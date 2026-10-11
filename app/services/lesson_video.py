import json
import re
import shutil
import subprocess
import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

import yaml
from app.constants import (
    LESSON_VIDEO_TASK_STALE_HOURS,
    LESSON_VIDEO_WAIT_TIMEOUT_SECONDS,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MEDIA_ROOT = REPO_ROOT / "media"
PLACEHOLDER_RE = re.compile(
    r"\[placeholder\].*?Limit the topics to what's in (?P<doc>.+?)\.\".*?\[/placeholder\]",
    re.DOTALL,
)


class LessonVideoError(Exception):
    pass


@dataclass
class VideoJobState:
    status: str  # "running" | "done" | "error"
    started_at: datetime
    error: str | None = None


_JOBS: dict[str, VideoJobState] = {}
_JOBS_LOCK = threading.Lock()
_NOTEBOOKLM_SOURCE_LOCK = threading.Lock()
_NOTEBOOKLM_GENERATION_LOCK = threading.Lock()


def _console_safe(value: str, encoding: str | None = None) -> str:
    target_encoding = encoding or getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        value.encode(target_encoding)
    except UnicodeEncodeError:
        return value.encode(target_encoding, errors="backslashreplace").decode(
            target_encoding
        )
    return value


def _print_console(value: str) -> None:
    print(_console_safe(value), flush=True)


class _HTMLTextExtractor(HTMLParser):
    _BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
    _SKIP_TAGS = {"noscript", "script", "style", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.body_parts: list[str] = []
        self.main_parts: list[str] = []
        self.title_parts: list[str] = []
        self.canonical_url: str | None = None
        self.saw_main = False
        self._main_depth = 0
        self._skip_depth = 0
        self._title_depth = 0

    def _append(self, value: str) -> None:
        self.body_parts.append(value)
        if self._main_depth:
            self.main_parts.append(value)

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.casefold()
        if self._skip_depth:
            if tag in self._SKIP_TAGS:
                self._skip_depth += 1
            return
        if tag in self._SKIP_TAGS:
            self._skip_depth = 1
            return
        if tag == "main":
            self.saw_main = True
            self._main_depth += 1
        if tag == "title":
            self._title_depth += 1
        if tag == "link" and self.canonical_url is None:
            attributes = {name.casefold(): value for name, value in attrs}
            rel = (attributes.get("rel") or "").casefold().split()
            href = attributes.get("href")
            if "canonical" in rel and href:
                self.canonical_url = href
        if tag in self._BLOCK_TAGS:
            self._append("\n")

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if self._skip_depth:
            if tag in self._SKIP_TAGS:
                self._skip_depth -= 1
            return
        if tag in self._BLOCK_TAGS:
            self._append("\n")
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        if tag == "main" and self._main_depth:
            self._main_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._append(data)
        if self._title_depth:
            self.title_parts.append(data)


def _notebooklm_profile() -> str:
    from app.config import get_settings

    profile = get_settings().notebooklm_profile.strip()
    if not profile:
        raise LessonVideoError("LEARNUP_NOTEBOOKLM_PROFILE no puede estar vacío.")
    return profile


def _notebooklm_cmd(*args: str) -> list[str]:
    return ["notebooklm", "--profile", _notebooklm_profile(), *args]


def _job_key(topic_slug: str, lesson_slug: str) -> str:
    return f"{topic_slug}:{lesson_slug}"


def find_lesson_path(topic_slug: str, lesson_slug: str) -> Path:
    matches = list(
        (REPO_ROOT / "content" / topic_slug / "lessons").rglob(f"{lesson_slug}.md")
    )
    if len(matches) != 1:
        raise LessonVideoError(
            f"Se esperaba una sola lección para el slug {lesson_slug!r}; se encontraron {len(matches)}."
        )
    return matches[0]


def find_lesson_slug_by_objective(topic_slug: str, objective: str) -> str:
    matches = list(
        (REPO_ROOT / "content" / topic_slug / "lessons" / objective).glob("*.md")
    )
    if len(matches) != 1:
        raise LessonVideoError(
            f"Se esperaba una sola lección para el objetivo {objective!r}; se encontraron {len(matches)}."
        )
    return matches[0].stem


def read_topic_name(topic_slug: str) -> str:
    syllabus_path = REPO_ROOT / "content" / topic_slug / "syllabus.yaml"
    return yaml.safe_load(syllabus_path.read_text(encoding="utf-8"))["topic_name"]


def read_notebooklm_output_language(topic_slug: str) -> str:
    syllabus_path = REPO_ROOT / "content" / topic_slug / "syllabus.yaml"
    syllabus = yaml.safe_load(syllabus_path.read_text(encoding="utf-8"))
    language = syllabus.get("notebooklm_output_language")
    if not isinstance(language, str) or not language.strip():
        raise LessonVideoError(
            f"El syllabus {syllabus_path} debe declarar notebooklm_output_language con un valor."
        )
    return language.strip()


def build_video_instructions(title: str, source_document: str) -> str:
    return (
        f'Create a video titled "{title}". '
        f"Limit the topics to what's in {source_document}, and pick up to 6 topics to cover "
        "from that document."
    )


def get_job_status(topic_slug: str, lesson_slug: str) -> dict:
    key = _job_key(topic_slug, lesson_slug)
    with _JOBS_LOCK:
        job = _JOBS.get(key)
    if job is not None:
        return {"status": job.status, "error": job.error}
    video_path = MEDIA_ROOT / topic_slug / f"{lesson_slug}.mp4"
    if video_path.exists():
        return {"status": "done", "error": None}
    # No in-memory job (e.g. server restarted mid-generation) but Gemini Notebook may still be
    # working on a task we submitted earlier — surface it as running rather than idle so the
    # caller doesn't think generation was never requested.
    if _load_pending_task(topic_slug, lesson_slug) is not None:
        return {"status": "running", "error": None}
    return {"status": "idle", "error": None}


def start_generation(topic_slug: str, lesson_slug: str) -> None:
    key = _job_key(topic_slug, lesson_slug)
    with _JOBS_LOCK:
        existing = _JOBS.get(key)
        if existing is not None and existing.status == "running":
            raise LessonVideoError(
                "Ya hay una generación de video en curso para esta lección."
            )

    lesson_path = find_lesson_path(topic_slug, lesson_slug)
    if not PLACEHOLDER_RE.search(lesson_path.read_text(encoding="utf-8")):
        raise LessonVideoError("Esta lección ya tiene un video configurado.")

    with _JOBS_LOCK:
        _JOBS[key] = VideoJobState(status="running", started_at=datetime.now(UTC))
    threading.Thread(
        target=_run_job, args=(topic_slug, lesson_slug), daemon=True
    ).start()


def _run_job(topic_slug: str, lesson_slug: str) -> None:
    key = _job_key(topic_slug, lesson_slug)
    try:
        generate_lesson_video(topic_slug, lesson_slug)
        with _JOBS_LOCK:
            _JOBS[key] = VideoJobState(status="done", started_at=_JOBS[key].started_at)
    except (
        Exception
    ) as exc:  # surfaced to the frontend via get_job_status, not swallowed
        _print_console(
            f"[video] generation failed for {topic_slug}/{lesson_slug}: {exc}"
        )
        _print_console(traceback.format_exc().rstrip())
        with _JOBS_LOCK:
            _JOBS[key] = VideoJobState(
                status="error", started_at=_JOBS[key].started_at, error=str(exc)
            )


def _run_captured(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    result.stdout = result.stdout or ""
    result.stderr = result.stderr or ""
    return result


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    result = _run_captured(cmd)
    _print_console(
        f"[video] notebooklm command exited {result.returncode}: {' '.join(cmd)}"
    )
    if result.stdout.strip():
        _print_console(f"[video] notebooklm stdout:\n{result.stdout.rstrip()}")
    if result.stderr.strip():
        _print_console(f"[video] notebooklm stderr:\n{result.stderr.rstrip()}")
    if result.returncode != 0:
        output = result.stderr or result.stdout
        if "RateLimitError" in output or "Rate limited" in output:
            raise LessonVideoError(
                "Gemini Notebook limitó temporalmente la generación de videos. Intentá más tarde."
            )
        raise LessonVideoError(
            f"El comando falló ({result.returncode}): {' '.join(cmd)}\n{output}"
        )
    return result


def _ensure_notebooklm_cli() -> None:
    if shutil.which("notebooklm") is None:
        raise LessonVideoError(
            "La CLI `notebooklm` no está instalada. Ejecutá `uv sync --group notebooklm` y luego "
            "`uv run notebooklm login`, o usá la alternativa manual indicada en la lección."
        )
    check = _run_captured(
        _notebooklm_cmd("auth", "check", "--test", "--json")
    )
    _print_console(f"[video] notebooklm auth check exited {check.returncode}")
    if check.stdout.strip():
        _print_console(f"[video] notebooklm auth stdout:\n{check.stdout.rstrip()}")
    if check.stderr.strip():
        _print_console(f"[video] notebooklm auth stderr:\n{check.stderr.rstrip()}")
    if check.returncode != 0:
        raise LessonVideoError(
            "No hay una sesión iniciada en Gemini Notebook. Ejecutá `uv run notebooklm login` y reintentá."
        )


def _set_notebooklm_output_language(language_code: str) -> None:
    result = _run(_notebooklm_cmd("language", "list", "--json"))
    try:
        languages = json.loads(result.stdout)["languages"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LessonVideoError(
            f"La salida de `notebooklm language list --json` no tiene el formato esperado: {result.stdout}"
        ) from exc
    if not isinstance(languages, dict) or not all(
        isinstance(code, str) and isinstance(name, str)
        for code, name in languages.items()
    ):
        raise LessonVideoError(
            f"La salida de `notebooklm language list --json` no tiene el formato esperado: {result.stdout}"
        )
    if language_code not in languages:
        supported = ", ".join(sorted(languages))
        raise LessonVideoError(
            f"NotebookLM no admite el idioma de salida {language_code!r}. "
            f"Códigos admitidos: {supported}"
        )
    _run(_notebooklm_cmd("language", "set", language_code, "--json"))
    _print_console(
        f"[video] NotebookLM output language set to {languages[language_code]} ({language_code})"
    )


def _get_or_create_notebook(topic_slug: str) -> str:
    state_file = MEDIA_ROOT / topic_slug / ".notebook.json"
    profile = _notebooklm_profile()
    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if state.get("profile", "default") == profile:
            return state["notebook_id"]
        _print_console(
            f"[video] NotebookLM profile changed from {state.get('profile', 'default')} to {profile}; "
            "creating a new topic notebook"
        )
    result = _run(_notebooklm_cmd("create", read_topic_name(topic_slug), "--json"))
    data = json.loads(result.stdout)
    notebook_id = (
        data.get("id") or data.get("notebook_id") or data.get("notebook", {}).get("id")
    )
    if not notebook_id:
        raise LessonVideoError(
            f"La salida de `notebooklm create` no contiene un ID de notebook: {result.stdout}"
        )
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({"notebook_id": notebook_id, "profile": profile}),
        encoding="utf-8",
    )
    added_file = MEDIA_ROOT / topic_slug / ".sources_added.json"
    if added_file.exists():
        added_file.unlink()
    return notebook_id


def _normalize_extracted_text(parts: list[str]) -> str:
    lines = []
    for raw_line in "".join(parts).splitlines():
        line = " ".join(raw_line.split())
        if line:
            lines.append(line)
    return "\n".join(lines)


def _convert_html_source(path: Path) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(path.read_text(encoding="utf-8"))
        parser.close()
    except (OSError, UnicodeError) as exc:
        raise LessonVideoError(
            f"No se pudo leer la fuente HTML {path.name!r} como UTF-8."
        ) from exc

    content = _normalize_extracted_text(
        parser.main_parts if parser.saw_main else parser.body_parts
    )
    if not content:
        raise LessonVideoError(
            f"La conversión de la fuente HTML {path.name!r} no produjo texto."
        )

    title = _normalize_extracted_text(parser.title_parts)
    header = [f"Fuente original: {path.name}"]
    if title:
        header.append(f"Título: {title}")
    if parser.canonical_url:
        header.append(f"URL canónica: {parser.canonical_url}")
    return "\n".join([*header, "", content, ""])


def _convert_json_source(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError) as exc:
        raise LessonVideoError(
            f"No se pudo convertir la fuente JSON {path.name!r}."
        ) from exc
    formatted = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    return f"Fuente original: {path.name}\n\n{formatted}\n"


def _prepare_source_for_notebook(topic_slug: str, path: Path) -> Path:
    suffix = path.suffix.casefold()
    converters = {
        ".htm": _convert_html_source,
        ".html": _convert_html_source,
        ".json": _convert_json_source,
    }
    converter = converters.get(suffix)
    if converter is None:
        return path

    prepared_dir = REPO_ROOT / ".learnup-cache" / topic_slug / "notebook_sources"
    prepared_path = prepared_dir / f"{path.name}.txt"
    converted = converter(path)
    prepared_dir.mkdir(parents=True, exist_ok=True)
    if not prepared_path.exists() or prepared_path.read_text(encoding="utf-8") != converted:
        prepared_path.write_text(converted, encoding="utf-8", newline="\n")
    return prepared_path


def _list_notebook_source_titles(notebook_id: str) -> set[str]:
    result = _run(
        _notebooklm_cmd("source", "list", "--notebook", notebook_id, "--json")
    )
    try:
        sources = json.loads(result.stdout)["sources"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LessonVideoError(
            "La salida de `notebooklm source list --json` no tiene el formato esperado: "
            f"{result.stdout}"
        ) from exc
    if not isinstance(sources, list):
        raise LessonVideoError(
            "La salida de `notebooklm source list --json` no tiene el formato esperado: "
            f"{result.stdout}"
        )

    titles: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("title"), str):
            raise LessonVideoError(
                "La salida de `notebooklm source list --json` contiene una fuente inválida: "
                f"{result.stdout}"
            )
        titles.add(source["title"])
    return titles


def _read_added_sources(added_file: Path) -> set[str]:
    if not added_file.exists():
        return set()
    try:
        data = json.loads(added_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError) as exc:
        raise LessonVideoError(
            f"No se pudo leer el estado de fuentes sincronizadas en {added_file}."
        ) from exc
    if not isinstance(data, list) or not all(isinstance(name, str) for name in data):
        raise LessonVideoError(
            f"El estado de fuentes sincronizadas en {added_file} no es una lista de nombres."
        )
    return set(data)


def _write_added_sources(added_file: Path, added: set[str]) -> None:
    added_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = added_file.with_name(f"{added_file.name}.tmp")
    temporary_file.write_text(
        json.dumps(sorted(added)), encoding="utf-8", newline="\n"
    )
    temporary_file.replace(added_file)


def _sync_sources(topic_slug: str, notebook_id: str) -> None:
    sources_dir = REPO_ROOT / "sources" / topic_slug
    added_file = MEDIA_ROOT / topic_slug / ".sources_added.json"
    added = _read_added_sources(added_file)
    skip = {"INTAKE.md", "SOURCES.md"}
    sources = [
        (path, _prepare_source_for_notebook(topic_slug, path))
        for path in sorted(sources_dir.iterdir())
        if path.is_file() and path.name not in skip
    ]
    remote_titles = _list_notebook_source_titles(notebook_id)
    for path, upload_path in sources:
        if path.name in added:
            continue
        if upload_path.name not in remote_titles:
            _run(
                _notebooklm_cmd(
                    "source", "add", str(upload_path), "--notebook", notebook_id
                )
            )
            remote_titles.add(upload_path.name)
        added.add(path.name)
        _write_added_sources(added_file, added)
    _write_added_sources(added_file, added)


def _pending_tasks_file(topic_slug: str) -> Path:
    return MEDIA_ROOT / topic_slug / ".video_tasks.json"


def _is_stale(started_at: str) -> bool:
    age = datetime.now(UTC) - datetime.fromisoformat(started_at)
    return age > timedelta(hours=LESSON_VIDEO_TASK_STALE_HOURS)


def _load_pending_task(topic_slug: str, lesson_slug: str) -> str | None:
    tasks_file = _pending_tasks_file(topic_slug)
    if not tasks_file.exists():
        return None
    entry = json.loads(tasks_file.read_text(encoding="utf-8")).get(lesson_slug)
    if entry is None:
        return None
    # `started_at` is missing for entries saved before this field existed — treat those as stale
    # too (we have no way to know their age, and the safe assumption is that anything without a
    # timestamp is old). A task this old getting reported as "running" forever is exactly the bug
    # this staleness check exists to close: the run that saved it crashed or errored without ever
    # calling `_clear_pending_task`, so the entry outlives the actual (long-finished-or-abandoned)
    # generation and makes the UI show "Generating…" indefinitely for a lesson nothing is doing.
    started_at = entry.get("started_at") if isinstance(entry, dict) else None
    if started_at is None or _is_stale(started_at):
        _clear_pending_task(topic_slug, lesson_slug)
        return None
    return entry["task_id"]


def _save_pending_task(topic_slug: str, lesson_slug: str, task_id: str) -> None:
    tasks_file = _pending_tasks_file(topic_slug)
    tasks = (
        json.loads(tasks_file.read_text(encoding="utf-8"))
        if tasks_file.exists()
        else {}
    )
    tasks[lesson_slug] = {
        "task_id": task_id,
        "started_at": datetime.now(UTC).isoformat(),
    }
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    tasks_file.write_text(json.dumps(tasks), encoding="utf-8")


def _clear_pending_task(topic_slug: str, lesson_slug: str) -> None:
    tasks_file = _pending_tasks_file(topic_slug)
    if not tasks_file.exists():
        return
    tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
    tasks.pop(lesson_slug, None)
    tasks_file.write_text(json.dumps(tasks), encoding="utf-8")


def _generate_and_download(
    topic_slug: str,
    lesson_slug: str,
    notebook_id: str,
    instructions: str,
    output_language: str,
) -> Path:
    out_path = MEDIA_ROOT / topic_slug / f"{lesson_slug}.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Check for a task already started in a previous (possibly crashed/rebooted) run before
    # asking Gemini Notebook to generate another one — video generation eats one of a handful of
    # daily quota slots, so re-requesting on every retry would burn quota and leave duplicate
    # artifacts sitting in the notebook.
    task_id = _load_pending_task(topic_slug, lesson_slug)
    if task_id is None:
        # NotebookLM's output language is global to the selected account. Keep setting it and
        # submitting the generation request in one critical section so concurrent topics cannot
        # switch the language between these two commands.
        with _NOTEBOOKLM_GENERATION_LOCK:
            _set_notebooklm_output_language(output_language)
            result = _run(
                _notebooklm_cmd(
                    "generate",
                    "video",
                    instructions,
                    "--notebook",
                    notebook_id,
                    "--style",
                    "whiteboard",
                    "--json",
                )
            )
        task_id = json.loads(result.stdout)["task_id"]
        # Persisted immediately, before the (multi-minute) wait below — so a killed process or
        # a reboot mid-wait doesn't lose track of a generation that's already in flight server-side.
        _save_pending_task(topic_slug, lesson_slug, task_id)

    wait_result = _run(
        _notebooklm_cmd(
            "artifact",
            "wait",
            task_id,
            "--notebook",
            notebook_id,
            "--timeout",
            str(LESSON_VIDEO_WAIT_TIMEOUT_SECONDS),
        )
    )
    if re.search(
        r"^Status:\s*failed\s*$", wait_result.stdout, re.IGNORECASE | re.MULTILINE
    ):
        _clear_pending_task(topic_slug, lesson_slug)
        raise LessonVideoError(
            f"Falló el artefacto de video de NotebookLM (tarea {task_id}). "
            "Revisá el notebook para ver el detalle informado por el proveedor."
        )
    _run(
        _notebooklm_cmd(
            "download",
            "video",
            str(out_path),
            "--notebook",
            notebook_id,
            "--artifact",
            task_id,
            "--force",
        )
    )
    if not out_path.exists():
        raise LessonVideoError(
            "La descarga informó éxito, pero no se encontró el archivo de salida."
        )
    _clear_pending_task(topic_slug, lesson_slug)
    return out_path


def generate_lesson_video(topic_slug: str, lesson_slug: str) -> Path:
    lesson_path = find_lesson_path(topic_slug, lesson_slug)
    text = lesson_path.read_text(encoding="utf-8")
    match = PLACEHOLDER_RE.search(text)
    if not match:
        raise LessonVideoError("Esta lección ya tiene un video configurado.")

    # Lazy: app.db opens a DuckDB connection at import time (single-writer), so only pull it in
    # once we're actually about to write — not on every import of this module (--dry-run etc).
    from app.content.seed import load_lesson_file, split_why_it_matters
    from app.db import SessionLocal
    from app.models import Lesson
    from sqlalchemy import select

    frontmatter, _ = load_lesson_file(lesson_path)
    title = frontmatter.get("title", lesson_slug)
    instructions = build_video_instructions(title, match.group("doc"))
    output_language = read_notebooklm_output_language(topic_slug)
    _print_console(
        f"[video] Gemini Notebook prompt for {topic_slug}/{lesson_slug}: {instructions}"
    )

    _ensure_notebooklm_cli()
    notebook_id = _get_or_create_notebook(topic_slug)
    with _NOTEBOOKLM_SOURCE_LOCK:
        _sync_sources(topic_slug, notebook_id)
    video_path = _generate_and_download(
        topic_slug, lesson_slug, notebook_id, instructions, output_language
    )

    link = f"[Ver el resumen en video](/media/{topic_slug}/{lesson_slug}.mp4)"
    lesson_path.write_text(
        PLACEHOLDER_RE.sub(link, text, count=1),
        encoding="utf-8",
        newline="\n",
    )

    _, body = load_lesson_file(lesson_path)
    main_body, why = split_why_it_matters(body)
    with SessionLocal() as session:
        lesson = session.execute(
            select(Lesson).where(Lesson.slug == lesson_slug)
        ).scalar_one()
        lesson.body_markdown = main_body
        lesson.why_it_matters_markdown = why
        session.commit()

    return video_path
