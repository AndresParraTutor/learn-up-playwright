from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

from pypdf import PdfReader

INSUFFICIENT_CONTEXT_SENTINEL = "INSUFFICIENT_CONTEXT"
REPO_ROOT = Path(__file__).resolve().parents[3]
_SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".mp3",
    ".wav",
    ".mp4",
    ".mov",
    ".avi",
    ".zip",
}


class LessonQAError(RuntimeError):
    pass


def topic_sources_markdown(topic_slug: str) -> str:
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", topic_slug) is None:
        raise LessonQAError("Slug de tema inválido.")
    source_root = REPO_ROOT / "sources" / topic_slug
    if not source_root.is_dir():
        raise LessonQAError(f"No existe el directorio de fuentes de {topic_slug}.")
    sections: list[str] = []
    omitted: list[str] = []
    for path in sorted(value for value in source_root.rglob("*") if value.is_file()):
        relative = path.relative_to(source_root).as_posix()
        if relative in {"INTAKE.md", "SOURCES.md"}:
            continue
        if path.suffix.lower() in _SKIP_SUFFIXES:
            omitted.append(relative)
            continue
        if path.suffix.lower() == ".pdf":
            try:
                reader = PdfReader(path)
                text = "\n".join((page.extract_text() or "") for page in reader.pages)
            except Exception as exc:
                raise LessonQAError(f"No se pudo extraer texto de {relative}: {exc}") from exc
            if not text.strip():
                raise LessonQAError(f"El PDF {relative} no contiene texto extraíble.")
        else:
            try:
                text = path.read_text(encoding="utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise LessonQAError(
                    f"La fuente {relative} no es UTF-8 ni un recurso multimedia reconocido."
                ) from exc
        sections.append(f"## Fuente: {relative}\n\n{text.strip()}")
    if omitted:
        sections.append(
            "## Recursos no textuales omitidos\n\n"
            + "\n".join(f"- {name}" for name in omitted)
        )
    if not sections:
        raise LessonQAError(f"No hay fuentes utilizables para {topic_slug}.")
    return "\n\n".join(sections)


def build_prompt(
    context: str,
    selected_text: str,
    question: str,
    *,
    allow_insufficient: bool,
) -> str:
    insufficiency = (
        f"Si el documento no alcanza para responder con confianza, respondé únicamente "
        f"la línea literal {INSUFFICIENT_CONTEXT_SENTINEL}."
        if allow_insufficient
        else "Si la respuesta no aparece en las fuentes, indicá claramente esa limitación sin inventar."
    )
    return f"""Respondé en español latinoamericano usando exclusivamente el material proporcionado.
{insufficiency}
La primera línea debe comenzar con Title: seguida por una reformulación breve y clara de la pregunta.
Después dejá una línea en blanco y escribí la respuesta en prosa Markdown.
No envuelvas la respuesta en etiquetas, corchetes ni marcadores.

Pasaje seleccionado:
{selected_text}

Pregunta:
{question}

Material autorizado:
{context}
"""


def _parse_answer(raw: str) -> tuple[str, str]:
    value = raw.strip()
    lines = value.splitlines()
    if not lines or not lines[0].startswith("Title: "):
        raise LessonQAError("La respuesta del modelo no comenzó con Title: .")
    title = lines[0][len("Title: ") :].strip()
    answer = "\n".join(lines[1:]).strip()
    answer = re.sub(r"^<answer>\s*", "", answer, flags=re.IGNORECASE)
    answer = re.sub(r"\s*</answer>$", "", answer, flags=re.IGNORECASE)
    if not title or not answer:
        raise LessonQAError("La respuesta del modelo no tiene título o cuerpo.")
    return title, answer


def ask(
    context: str,
    selected_text: str,
    question: str,
    *,
    allow_insufficient: bool,
    backend: ModuleType | None = None,
) -> Iterator[dict[str, str]]:
    if backend is None:
        from app.services.lesson_qa.backends import get_backend

        backend = get_backend()
    backend.check_available()
    prompt = build_prompt(
        context, selected_text, question, allow_insufficient=allow_insufficient
    )
    iterator = iter(backend.stream(prompt))
    deltas: list[str] = []
    while True:
        try:
            delta = next(iterator)
        except StopIteration as stop:
            authoritative = stop.value
            break
        if delta:
            text = str(delta)
            deltas.append(text)
            yield {"type": "delta", "text": text}
    raw = str(authoritative or "".join(deltas)).strip()
    if raw == INSUFFICIENT_CONTEXT_SENTINEL:
        yield {"type": "insufficient"}
        return
    title, answer = _parse_answer(raw)
    yield {"type": "result", "title": title, "answer": answer}
