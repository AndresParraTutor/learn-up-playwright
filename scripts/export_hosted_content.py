from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
FAQ_MARKER = "\n## FAQ\n"
WHY_MARKER = "\n## Why It Matters\n"
TOPIC_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
LESSON_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


class HostedExportError(ValueError):
    pass


def _read_utf8(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise HostedExportError(f"No se pudo leer {path} como UTF-8: {exc}") from exc
    if not value.strip():
        raise HostedExportError(f"El archivo requerido {path} está vacío.")
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(_read_utf8(path))
    except yaml.YAMLError as exc:
        raise HostedExportError(f"YAML inválido en {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HostedExportError(f"{path} debe contener un objeto YAML.")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read_utf8(path))
    except json.JSONDecodeError as exc:
        raise HostedExportError(f"JSON inválido en {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HostedExportError(f"{path} debe contener un objeto JSON.")
    return value


def _required_text(value: object, label: str) -> str:
    if value is None:
        raise HostedExportError(f"Falta {label}.")
    text = str(value).strip()
    if not text:
        raise HostedExportError(f"{label} no puede estar vacío.")
    return text


def _required_list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise HostedExportError(f"{label} debe ser una lista.")
    return value


def _stable_id(topic_slug: str, kind: str, key: str) -> str:
    if ":" in key or not key.strip():
        raise HostedExportError(f"Clave estable inválida para {kind}: {key!r}")
    return f"topic:{topic_slug}:{kind}:{key}"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _repo_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise HostedExportError(f"La ruta está fuera del repositorio: {path}") from exc


def _parse_lesson(path: Path) -> tuple[dict[str, Any], str, str]:
    match = LESSON_RE.match(_read_utf8(path))
    if match is None:
        raise HostedExportError(f"Frontmatter inválido en {path}.")
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise HostedExportError(f"Frontmatter YAML inválido en {path}: {exc}") from exc
    if not isinstance(frontmatter, dict):
        raise HostedExportError(f"Frontmatter inválido en {path}.")
    authored = match.group(2).split(FAQ_MARKER, 1)[0].rstrip()
    if authored.count(WHY_MARKER) != 1:
        raise HostedExportError(
            f"{path} debe contener exactamente un encabezado Why It Matters."
        )
    body, why = authored.split(WHY_MARKER, 1)
    return frontmatter, body.strip(), why.strip()


def _source_entry(repo_root: Path, path: Path) -> dict[str, object]:
    return {
        "path": _repo_path(repo_root, path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def refresh_media_manifest(repo_root: Path, topic_slug: str) -> Path:
    if TOPIC_SLUG_RE.fullmatch(topic_slug) is None:
        raise HostedExportError(f"Slug de tema inválido: {topic_slug!r}")
    topic_root = repo_root / "content" / topic_slug
    media_root = repo_root / "media" / topic_slug
    syllabus = _load_yaml(topic_root / "syllabus.yaml")
    content_version = _required_text(
        syllabus.get("syllabus_version"), "syllabus_version"
    )
    objects: list[dict[str, object]] = []
    for path in sorted((topic_root / "lessons").glob("*/*.md")):
        slug = path.stem
        video_path = media_root / f"{slug}.mp4"
        available = video_path.is_file()
        objects.append(
            {
                "content_id": _stable_id(topic_slug, "lesson", slug),
                "object_key": f"media/{topic_slug}/{slug}.mp4",
                "source_path": _repo_path(repo_root, video_path),
                "available": available,
                "bytes": video_path.stat().st_size if available else None,
                "sha256": _sha256_file(video_path) if available else None,
                "content_type": "video/mp4",
            }
        )
    manifest = {
        "schema_version": 1,
        "topic_id": f"topic:{topic_slug}",
        "content_version": content_version,
        "present_count": sum(1 for item in objects if item["available"]),
        "missing_count": sum(1 for item in objects if not item["available"]),
        "objects": objects,
    }
    media_root.mkdir(parents=True, exist_ok=True)
    manifest_path = media_root / "manifest.json"
    manifest_path.write_bytes(_json_bytes(manifest))
    return manifest_path


def build_topic_artifacts(
    repo_root: Path, topic_slug: str
) -> dict[str, bytes]:
    if TOPIC_SLUG_RE.fullmatch(topic_slug) is None:
        raise HostedExportError(f"Slug de tema inválido: {topic_slug!r}")
    topic_root = repo_root / "content" / topic_slug
    media_root = repo_root / "media" / topic_slug
    media_manifest_path = media_root / "manifest.json"
    syllabus_path = topic_root / "syllabus.yaml"
    syllabus = _load_yaml(syllabus_path)
    if _required_text(syllabus.get("topic_slug"), "topic_slug") != topic_slug:
        raise HostedExportError("El topic_slug no coincide con el directorio del tema.")

    source_paths: set[Path] = {syllabus_path, media_manifest_path}
    topic_id = f"topic:{topic_slug}"
    content_version = _required_text(syllabus.get("syllabus_version"), "syllabus_version")
    domains: list[dict[str, object]] = []
    objective_ids: dict[str, str] = {}
    for domain_value in _required_list(syllabus.get("domains"), "domains"):
        if not isinstance(domain_value, dict):
            raise HostedExportError("Cada dominio debe ser un objeto.")
        domain_code = _required_text(domain_value.get("code"), "domain.code")
        domain_id = _stable_id(topic_slug, "domain", domain_code)
        objectives: list[dict[str, object]] = []
        for objective_value in _required_list(
            domain_value.get("objectives"), f"domain[{domain_code}].objectives"
        ):
            if not isinstance(objective_value, dict):
                raise HostedExportError("Cada objetivo debe ser un objeto.")
            objective_code = _required_text(
                objective_value.get("code"), "objective.code"
            )
            if objective_code in objective_ids:
                raise HostedExportError(f"Objetivo duplicado: {objective_code}")
            objective_id = _stable_id(topic_slug, "objective", objective_code)
            objective_ids[objective_code] = objective_id
            objectives.append(
                {
                    "id": objective_id,
                    "code": objective_code,
                    "domain_id": domain_id,
                    "title": _required_text(
                        objective_value.get("title"), f"objective[{objective_code}].title"
                    ),
                    "topics": [
                        _required_text(item, f"objective[{objective_code}].topics")
                        for item in _required_list(
                            objective_value.get("topics"),
                            f"objective[{objective_code}].topics",
                        )
                    ],
                    "content_version": content_version,
                }
            )
        domains.append(
            {
                "id": domain_id,
                "code": domain_code,
                "topic_id": topic_id,
                "name": _required_text(domain_value.get("name"), "domain.name"),
                "weight_pct": int(domain_value["weight_pct"]),
                "content_version": content_version,
                "objectives": objectives,
            }
        )
    if sum(int(domain["weight_pct"]) for domain in domains) != 100:
        raise HostedExportError("Los pesos de los dominios no suman 100.")

    lessons: list[dict[str, object]] = []
    media_manifest = _load_json(media_manifest_path)
    raw_media_objects = _required_list(media_manifest.get("objects"), "media.objects")
    media_by_content_id: dict[str, dict[str, Any]] = {}
    for value in raw_media_objects:
        if not isinstance(value, dict):
            raise HostedExportError("Cada objeto del manifiesto multimedia debe ser un objeto.")
        content_id = _required_text(value.get("content_id"), "media.content_id")
        if content_id in media_by_content_id:
            raise HostedExportError(f"Medio duplicado para {content_id}.")
        media_by_content_id[content_id] = value
    media_objects: list[dict[str, object]] = []
    for path in sorted((topic_root / "lessons").glob("*/*.md")):
        source_paths.add(path)
        frontmatter, body, why = _parse_lesson(path)
        objective_code = _required_text(frontmatter.get("objective"), "lesson.objective")
        if objective_code not in objective_ids:
            raise HostedExportError(f"Objetivo de lección desconocido en {path}.")
        slug = path.stem
        lesson_id = _stable_id(topic_slug, "lesson", slug)
        object_key = f"media/{topic_slug}/{slug}.mp4"
        video_path = media_root / f"{slug}.mp4"
        media_value = media_by_content_id.pop(lesson_id, None)
        if media_value is None:
            raise HostedExportError(
                f"Falta {lesson_id} en {media_manifest_path}; ejecutá --refresh-media."
            )
        expected_source = _repo_path(repo_root, video_path)
        if _required_text(media_value.get("object_key"), "media.object_key") != object_key:
            raise HostedExportError(f"Object key inválida para {lesson_id}.")
        if _required_text(media_value.get("source_path"), "media.source_path") != expected_source:
            raise HostedExportError(f"Ruta multimedia inválida para {lesson_id}.")
        available = bool(media_value.get("available"))
        expected_bytes = media_value.get("bytes")
        expected_sha256 = media_value.get("sha256")
        if video_path.is_file():
            if not available:
                raise HostedExportError(
                    f"Hay un video nuevo para {lesson_id}; ejecutá --refresh-media."
                )
            if expected_bytes != video_path.stat().st_size:
                raise HostedExportError(f"El tamaño cambió para {lesson_id}.")
            if expected_sha256 != _sha256_file(video_path):
                raise HostedExportError(f"El checksum cambió para {lesson_id}.")
        elif not available and (expected_bytes is not None or expected_sha256 is not None):
            raise HostedExportError(f"Metadatos inconsistentes para {lesson_id}.")
        lessons.append(
            {
                "id": lesson_id,
                "slug": slug,
                "topic_id": topic_id,
                "objective_id": objective_ids[objective_code],
                "objective_code": objective_code,
                "title": _required_text(frontmatter.get("title"), "lesson.title"),
                "body_markdown": body,
                "why_it_matters_markdown": why,
                "content_version": content_version,
                "video_object_key": object_key if available else None,
            }
        )
        media_objects.append(
            {
                "content_id": lesson_id,
                "object_key": object_key,
                "source_path": expected_source,
                "available": available,
                "bytes": expected_bytes,
                "sha256": expected_sha256,
                "content_type": "video/mp4",
            }
        )
    if media_by_content_id:
        raise HostedExportError(
            "El manifiesto multimedia contiene lecciones inexistentes: "
            + ", ".join(sorted(media_by_content_id))
        )

    questions: list[dict[str, object]] = []
    question_ids: dict[str, str] = {}
    for path in sorted((topic_root / "questions").glob("*.yaml")):
        source_paths.add(path)
        data = _load_yaml(path)
        objective_code = _required_text(data.get("objective"), "questions.objective")
        if objective_code not in objective_ids:
            raise HostedExportError(f"Objetivo de preguntas desconocido en {path}.")
        for value in _required_list(data.get("questions"), f"{path}.questions"):
            if not isinstance(value, dict):
                raise HostedExportError(f"Cada pregunta de {path} debe ser un objeto.")
            external_id = _required_text(value.get("external_id"), "question.external_id")
            if external_id in question_ids:
                raise HostedExportError(f"Pregunta duplicada: {external_id}")
            question_id = _stable_id(topic_slug, "question", external_id)
            question_ids[external_id] = question_id
            choices: list[dict[str, object]] = []
            for position, choice_value in enumerate(
                _required_list(value.get("choices"), f"question[{external_id}].choices")
            ):
                if not isinstance(choice_value, dict):
                    raise HostedExportError("Cada opción debe ser un objeto.")
                choices.append(
                    {
                        "id": f"{question_id}:choice:{position}",
                        "position": position,
                        "text_markdown": _required_text(
                            choice_value.get("text"), "choice.text"
                        ),
                        "correct": bool(choice_value.get("correct")),
                        "explanation_markdown": _required_text(
                            choice_value.get("explanation"), "choice.explanation"
                        ),
                    }
                )
            questions.append(
                {
                    "id": question_id,
                    "external_id": external_id,
                    "topic_id": topic_id,
                    "objective_id": objective_ids[objective_code],
                    "objective_code": objective_code,
                    "type": _required_text(value.get("type"), "question.type"),
                    "difficulty": int(value["difficulty"]),
                    "mock_eligible": bool(value.get("is_mock_eligible")),
                    "stem_markdown": _required_text(value.get("stem"), "question.stem"),
                    "explanation_markdown": _required_text(
                        value.get("explanation"), "question.explanation"
                    ),
                    "content_version": content_version,
                    "choices": choices,
                }
            )

    labs: list[dict[str, object]] = []
    for path in sorted((topic_root / "labs").glob("*/*.yaml")):
        source_paths.add(path)
        data = _load_yaml(path)
        objective_code = _required_text(data.get("objective"), "lab.objective")
        if objective_code not in objective_ids:
            raise HostedExportError(f"Objetivo de práctica desconocido en {path}.")
        slug = path.stem
        lab_id = _stable_id(topic_slug, "lab", slug)
        checks: list[dict[str, object]] = []
        for position, check_value in enumerate(
            _required_list(data.get("self_check"), f"lab[{slug}].self_check")
        ):
            if not isinstance(check_value, dict):
                raise HostedExportError("Cada autocontrol debe ser un objeto.")
            raw_value = check_value.get("value")
            checks.append(
                {
                    "id": f"{lab_id}:check:{position}",
                    "position": position,
                    "prompt_markdown": _required_text(
                        check_value.get("prompt"), "lab.check.prompt"
                    ),
                    "kind": _required_text(check_value.get("kind"), "lab.check.kind"),
                    "expected_value": None if raw_value is None else str(raw_value),
                    "case_sensitive": bool(check_value.get("case_sensitive", False)),
                }
            )
        labs.append(
            {
                "id": lab_id,
                "slug": slug,
                "topic_id": topic_id,
                "objective_id": objective_ids[objective_code],
                "objective_code": objective_code,
                "title": _required_text(data.get("title"), "lab.title"),
                "scenario_markdown": _required_text(data.get("scenario"), "lab.scenario"),
                "setup_sql": _required_text(data.get("setup_sql"), "lab.setup_sql"),
                "task_markdown": _required_text(data.get("task"), "lab.task"),
                "expected_result": _required_text(
                    data.get("expected_result"), "lab.expected_result"
                ),
                "content_version": content_version,
                "self_check": checks,
            }
        )

    mocks: list[dict[str, object]] = []
    for path in sorted((topic_root / "mocks").glob("*.yaml")):
        source_paths.add(path)
        data = _load_yaml(path)
        code = _required_text(data.get("code"), "mock.code")
        external_ids = [
            _required_text(item, f"mock[{code}].questions")
            for item in _required_list(data.get("questions"), f"mock[{code}].questions")
        ]
        missing = sorted(set(external_ids) - question_ids.keys())
        if missing:
            raise HostedExportError(f"Preguntas inexistentes en {path}: {missing}")
        mocks.append(
            {
                "id": _stable_id(topic_slug, "mock", code),
                "code": code,
                "topic_id": topic_id,
                "content_version": _required_text(
                    data.get("syllabus_version"), "mock.syllabus_version"
                ),
                "question_ids": [question_ids[value] for value in external_ids],
            }
        )

    about_paths = {
        "app_markdown": repo_root / "ABOUT.md",
        "intake_markdown": repo_root / "sources" / topic_slug / "INTAKE.md",
        "sources_markdown": repo_root / "sources" / topic_slug / "SOURCES.md",
        "content_changes_markdown": topic_root / "CHANGELOG.md",
    }
    source_paths.update(about_paths.values())
    project_path = repo_root / "pyproject.toml"
    source_paths.add(project_path)
    try:
        app_version = _required_text(
            tomllib.loads(_read_utf8(project_path))["project"]["version"],
            "project.version",
        )
    except (KeyError, tomllib.TOMLDecodeError) as exc:
        raise HostedExportError("pyproject.toml no contiene una versión válida.") from exc

    source_entries = [
        _source_entry(repo_root, path)
        for path in sorted(source_paths, key=lambda item: _repo_path(repo_root, item))
    ]
    source_tree_hash = _sha256_bytes(
        "\n".join(
            f"{entry['path']}:{entry['sha256']}" for entry in source_entries
        ).encode("utf-8")
    )
    course = {
        "schema_version": 1,
        "source_tree_sha256": source_tree_hash,
        "topic": {
            "id": topic_id,
            "slug": topic_slug,
            "name": _required_text(syllabus.get("topic_name"), "topic_name"),
            "description": _required_text(
                syllabus.get("objective_summary"), "objective_summary"
            ),
            "content_language": _required_text(
                syllabus.get("content_language"), "content_language"
            ),
            "content_version": content_version,
            "assessment": syllabus.get("assessment"),
            "modules": syllabus.get("modules"),
        },
        "counts": {
            "domains": len(domains),
            "objectives": len(objective_ids),
            "lessons": len(lessons),
            "questions": len(questions),
            "labs": len(labs),
            "mocks": len(mocks),
        },
        "domains": domains,
        "lessons": lessons,
        "questions": questions,
        "labs": labs,
        "mocks": mocks,
        "about": {
            "app_version": app_version,
            **{
                name: "" if name in {"intake_markdown", "content_changes_markdown"}
                else _read_utf8(path)
                for name, path in about_paths.items()
            },
        },
    }
    media = {
        "schema_version": 1,
        "topic_id": topic_id,
        "content_version": content_version,
        "present_count": sum(1 for item in media_objects if item["available"]),
        "missing_count": sum(1 for item in media_objects if not item["available"]),
        "objects": media_objects,
    }
    seed_name = f"{topic_slug}.seed.json"
    media_name = f"{topic_slug}.media.json"
    seed_bytes = _json_bytes(course)
    media_bytes = _json_bytes(media)
    build_manifest = {
        "schema_version": 1,
        "topic_id": topic_id,
        "content_version": content_version,
        "source_tree_sha256": source_tree_hash,
        "inputs": source_entries,
        "outputs": [
            {
                "path": f"hosted/generated/{seed_name}",
                "bytes": len(seed_bytes),
                "sha256": _sha256_bytes(seed_bytes),
            },
            {
                "path": f"hosted/generated/{media_name}",
                "bytes": len(media_bytes),
                "sha256": _sha256_bytes(media_bytes),
            },
        ],
    }
    return {
        seed_name: seed_bytes,
        media_name: media_bytes,
        f"{topic_slug}.build-manifest.json": _json_bytes(build_manifest),
    }


def export_topic(
    repo_root: Path,
    topic_slug: str,
    output_dir: Path,
    *,
    check: bool,
) -> None:
    artifacts = build_topic_artifacts(repo_root, topic_slug)
    if check:
        mismatches = [
            name
            for name, expected in artifacts.items()
            if not (output_dir / name).is_file()
            or (output_dir / name).read_bytes() != expected
        ]
        if mismatches:
            raise HostedExportError(
                "Los artefactos alojados no están actualizados: " + ", ".join(mismatches)
            )
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in artifacts.items():
        (output_dir / name).write_bytes(value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exporta contenido determinista para la edición alojada de Learn-Up."
    )
    parser.add_argument("topic_slug")
    parser.add_argument(
        "--output-dir", type=Path, default=REPO_ROOT / "hosted" / "generated"
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--refresh-media", action="store_true")
    args = parser.parse_args()
    if args.check and args.refresh_media:
        parser.error("--check y --refresh-media no se pueden combinar.")
    try:
        if args.refresh_media:
            refresh_media_manifest(REPO_ROOT, args.topic_slug)
        export_topic(
            REPO_ROOT,
            args.topic_slug,
            args.output_dir,
            check=args.check,
        )
    except HostedExportError as exc:
        parser.error(str(exc))
    action = "verificados" if args.check else "generados"
    print(f"Artefactos alojados {action}: {args.topic_slug}")


if __name__ == "__main__":
    main()
