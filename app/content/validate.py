from __future__ import annotations

import logging
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path

import yaml

from app.content import faq
from app.content.seed import load_lesson_file
from app.services.topic_transfer import IMPLEMENTATION_ID

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_VERSION_RE = re.compile(r"[1-9]\d*\.\d*")
CORRECT_PREFIX = "Correct — "
PLACEHOLDER_RE = re.compile(
    r'^\[placeholder\]Upload this document and the documents in /sources to Gemini Notebook '
    r'and ask it to create a video summary with the prompt "Limit the topics to what\'s in '
    r'[^"]+\.", then put it here\. There\'s no drag-and-drop: click Generate Video above to do '
    r'this automatically, or if you generate the video yourself, either ask your LLM assistant '
    r'to place it, or do it yourself — save the download as media/(?P<topic>[a-z0-9-]+)/'
    r'(?P<slug>[a-z0-9-]+)\.mp4, replace this entire placeholder block with a markdown video '
    r'link to that file, then re-seed the content\.\[/placeholder\]$'
)


class ContentValidationError(RuntimeError):
    pass


def _yaml(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ContentValidationError(f"No se pudo leer {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContentValidationError(f"{path} debe contener un objeto YAML.")
    return value


def _require_text(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ContentValidationError(f"No se pudo leer {path}: {exc}") from exc
    if not value.strip():
        raise ContentValidationError(f"{path} está vacío.")
    return value


def _weighted_counts(domains: list[dict], count: int) -> dict[str, int]:
    exact = [
        (str(domain["code"]), count * int(domain["weight_pct"]) / 100)
        for domain in domains
    ]
    result = {code: int(value) for code, value in exact}
    remaining = count - sum(result.values())
    ranked = sorted(exact, key=lambda item: (item[1] - int(item[1])), reverse=True)
    for code, _ in ranked[:remaining]:
        result[code] += 1
    return result


def _validate_about(repo_root: Path, slug: str) -> None:
    sources_root = repo_root / "sources" / slug
    intake = _require_text(sources_root / "INTAKE.md")
    sources = _require_text(sources_root / "SOURCES.md")
    changes = _require_text(repo_root / "content" / slug / "CHANGELOG.md")
    if "# Intake" not in intake or "| Parameter | Value |" not in intake:
        raise ContentValidationError("INTAKE.md no conserva el contrato de configuración.")
    required_values = [
        "Topic slug",
        "Current knowledge",
        "Objective",
        "Content language",
        "NotebookLM output language",
        "FAQ LLM backend",
        "Assessment enabled",
        "Strategy enabled",
        "Labs enabled",
    ]
    for value in required_values:
        if value not in intake:
            raise ContentValidationError(f"INTAKE.md no registra {value}.")
    if "# Fuentes" not in sources or "Origen" not in sources or "Limitaciones" not in sources:
        raise ContentValidationError("SOURCES.md no conserva el catálogo y sus limitaciones.")
    if "Historial de cambios" not in changes:
        raise ContentValidationError("CHANGELOG.md no tiene el encabezado esperado.")

    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return
    project = tomllib.loads(_require_text(pyproject)).get("project", {})
    version = str(project.get("version", ""))
    if APP_VERSION_RE.fullmatch(version) is None:
        raise ContentValidationError("La versión de la aplicación debe tener forma MAJOR.MINOR.")
    _require_text(repo_root / "ABOUT.md")
    history_path = repo_root / ".local" / "ABOUT.md"
    if not history_path.is_file():
        return
    about = _require_text(history_path)
    if "## Historial de versiones" not in about and "## Version history" not in about:
        raise ContentValidationError("ABOUT.md no contiene el historial de versiones.")
    if re.search(rf"^### {re.escape(version)} — \d{{4}}-\d{{2}}-\d{{2}}$", about, re.MULTILINE) is None:
        raise ContentValidationError(
            f"ABOUT.md no registra la versión vigente {version} con fecha."
        )


def validate_topic_tree(repo_root: Path, slug: str) -> dict[str, int]:
    repo_root = repo_root.resolve()
    topic_root = (repo_root / "content" / slug).resolve()
    if topic_root.parent != (repo_root / "content").resolve() or not topic_root.is_dir():
        raise ContentValidationError(f"Ruta de tema inválida: {slug}")
    syllabus = _yaml(topic_root / "syllabus.yaml")
    if syllabus.get("topic_slug") != slug:
        raise ContentValidationError("topic_slug no coincide con el directorio.")
    if not str(syllabus.get("topic_name", "")).strip():
        raise ContentValidationError("topic_name no puede estar vacío.")
    if not str(syllabus.get("objective_summary", "")).strip():
        raise ContentValidationError("objective_summary no puede estar vacío.")
    if not str(syllabus.get("content_language", "")).strip():
        raise ContentValidationError("content_language no puede estar vacío.")
    if not str(syllabus.get("notebooklm_output_language", "")).strip():
        raise ContentValidationError("notebooklm_output_language no puede estar vacío.")
    domains = syllabus.get("domains")
    if not isinstance(domains, list) or not domains:
        raise ContentValidationError("El syllabus debe contener dominios.")
    if sum(int(domain["weight_pct"]) for domain in domains) != 100:
        raise ContentValidationError("Los pesos de dominio deben sumar 100.")

    objective_to_domain: dict[str, str] = {}
    for domain in domains:
        domain_code = str(domain["code"])
        for objective in domain.get("objectives", []):
            code = str(objective["code"])
            if code in objective_to_domain:
                raise ContentValidationError(f"Objetivo duplicado: {code}")
            if not code.startswith(domain_code + "."):
                raise ContentValidationError(f"Objetivo {code} fuera del dominio {domain_code}.")
            if not objective.get("topics"):
                raise ContentValidationError(f"Objetivo {code} sin temas.")
            objective_to_domain[code] = domain_code
    if not objective_to_domain:
        raise ContentValidationError("El syllabus no contiene objetivos.")

    lesson_counts: Counter[str] = Counter()
    for path in sorted((topic_root / "lessons").glob("*/*.md")):
        frontmatter, body = load_lesson_file(path)
        code = str(frontmatter.get("objective", ""))
        if code not in objective_to_domain or path.parent.name != code:
            raise ContentValidationError(f"Lección con objetivo colgante: {path}")
        if not str(frontmatter.get("title", "")).strip():
            raise ContentValidationError(f"Lección sin título: {path}")
        if body.count("## Why It Matters") != 1:
            raise ContentValidationError(
                f"La lección {path} debe tener un único ## Why It Matters."
            )
        first = next((line.strip() for line in body.splitlines() if line.strip()), "")
        if first.startswith("[placeholder]"):
            match = PLACEHOLDER_RE.fullmatch(first)
            if match is None:
                raise ContentValidationError(f"Placeholder inválido en {path}.")
            if match.group("topic") != slug or match.group("slug") != path.stem:
                raise ContentValidationError(f"Ruta del video incorrecta en {path}.")
        elif f"](/media/{slug}/{path.stem}.mp4)" not in first:
            raise ContentValidationError(
                f"La primera línea de {path} no es placeholder ni enlace de video."
            )
        mirrored = faq.faq_from_lesson_text(body)
        if mirrored:
            faq.parse_faq_entries(mirrored)
        lesson_counts[code] += 1
    for code in objective_to_domain:
        if lesson_counts[code] < 1:
            raise ContentValidationError(f"El objetivo {code} no tiene lección.")

    question_counts: Counter[str] = Counter()
    question_domain: dict[str, str] = {}
    eligible: set[str] = set()
    correct_longest = 0
    total_questions = 0
    for path in sorted((topic_root / "questions").glob("*.yaml")):
        data = _yaml(path)
        code = str(data.get("objective", ""))
        if code not in objective_to_domain or path.stem != code:
            raise ContentValidationError(f"Archivo de preguntas colgante: {path}")
        items = data.get("questions")
        if not isinstance(items, list):
            raise ContentValidationError(f"questions debe ser una lista en {path}.")
        for question in items:
            if not isinstance(question, dict):
                raise ContentValidationError(f"Pregunta inválida en {path}.")
            total_questions += 1
            external_id = str(question["external_id"])
            if external_id in question_domain or not external_id.startswith(code + "-"):
                raise ContentValidationError(f"ID de pregunta inválido o duplicado: {external_id}")
            question_type = str(question["type"])
            choices = question.get("choices")
            if question_type not in {"single", "multi"} or not isinstance(choices, list):
                raise ContentValidationError(f"Pregunta inválida: {external_id}")
            if len(choices) != 4:
                raise ContentValidationError(f"{external_id} debe tener cuatro opciones.")
            if not str(question.get("stem") or "").strip():
                raise ContentValidationError(f"{external_id} no tiene enunciado.")
            if not str(question.get("explanation") or "").strip():
                raise ContentValidationError(f"{external_id} no tiene explicación general.")
            correct = [choice for choice in choices if choice.get("correct") is True]
            if question_type == "single" and len(correct) != 1:
                raise ContentValidationError(f"{external_id} single no tiene una correcta.")
            if question_type == "multi" and len(correct) < 2:
                raise ContentValidationError(f"{external_id} multi necesita dos correctas.")
            for position, choice in enumerate(choices):
                if not isinstance(choice, dict):
                    raise ContentValidationError(
                        f"Opción {position + 1} inválida en {external_id}."
                    )
                if not str(choice.get("text") or "").strip():
                    raise ContentValidationError(
                        f"Opción {position + 1} sin texto en {external_id}."
                    )
                if not isinstance(choice.get("correct"), bool):
                    raise ContentValidationError(
                        f"Opción {position + 1} sin correct booleano en {external_id}."
                    )
                explanation = str(choice.get("explanation") or "").strip()
                if not explanation:
                    raise ContentValidationError(
                        f"Opción {position + 1} sin explicación en {external_id}."
                    )
                if choice.get("correct") is True and not explanation.startswith(
                    CORRECT_PREFIX
                ):
                    raise ContentValidationError(
                        f"Feedback correcto sin prefijo en {external_id}."
                    )
                if choice.get("correct") is not True and explanation.startswith(
                    CORRECT_PREFIX
                ):
                    raise ContentValidationError(
                        f"Un distractor usa el prefijo correcto en {external_id}."
                    )
            longest = max(len(str(choice["text"])) for choice in choices)
            if any(
                choice.get("correct") is True
                and len(str(choice["text"])) == longest
                for choice in choices
            ):
                correct_longest += 1
            if question.get("is_mock_eligible") is True:
                eligible.add(external_id)
            question_domain[external_id] = objective_to_domain[code]
            question_counts[code] += 1
    for code in objective_to_domain:
        if not 3 <= question_counts[code] <= 5:
            raise ContentValidationError(
                f"El objetivo {code} debe tener entre 3 y 5 preguntas."
            )
    if total_questions and correct_longest / total_questions > 2 / 3:
        raise ContentValidationError(
            "La respuesta correcta es la opción más larga en más de dos tercios de las preguntas."
        )

    lab_counts: Counter[str] = Counter()
    labs_enabled = bool(syllabus["modules"]["labs"])
    for path in sorted((topic_root / "labs").glob("*/*.yaml")):
        data = _yaml(path)
        code = str(data.get("objective", ""))
        if code not in objective_to_domain or path.parent.name != code:
            raise ContentValidationError(f"Laboratorio colgante: {path}")
        required = {
            "objective",
            "title",
            "scenario",
            "setup_sql",
            "task",
            "expected_result",
            "self_check",
        }
        if not required.issubset(data):
            raise ContentValidationError(f"Faltan campos en {path}.")
        checks = data["self_check"]
        if not isinstance(checks, list) or not checks:
            raise ContentValidationError(f"{path} no tiene autocontroles.")
        for check in checks:
            if check.get("kind") not in {
                "contains",
                "exact",
                "number_positive",
                "number_less_than_previous",
                "number_greater_than_previous",
            }:
                raise ContentValidationError(f"Tipo de autocontrol inválido en {path}.")
            if check.get("kind") in {"contains", "exact"} and "value" not in check:
                raise ContentValidationError(f"Autocontrol sin valor en {path}.")
        faq.faq_from_lab_data(data)
        lab_counts[code] += 1
    if labs_enabled:
        for code in objective_to_domain:
            if lab_counts[code] < 1:
                raise ContentValidationError(f"El objetivo {code} no tiene laboratorio.")

    assessment = syllabus["assessment"]
    mock_count = 0
    if bool(assessment["enabled"]):
        mocks = list((topic_root / "mocks").glob("*.yaml"))
        if len(mocks) != 1:
            raise ContentValidationError("Debe existir una evaluación fija.")
        mock = _yaml(mocks[0])
        mock_ids = [str(value) for value in mock["questions"]]
        expected_count = int(assessment["question_count"])
        if len(mock_ids) != expected_count or len(set(mock_ids)) != expected_count:
            raise ContentValidationError("Cantidad o unicidad inválida en el mock.")
        if any(question_id not in eligible for question_id in mock_ids):
            raise ContentValidationError("El mock referencia preguntas inexistentes/no elegibles.")
        actual = Counter(question_domain[question_id] for question_id in mock_ids)
        expected = _weighted_counts(domains, expected_count)
        if dict(actual) != expected:
            raise ContentValidationError(
                f"Distribución del mock incorrecta: {dict(actual)}; se esperaba {expected}."
            )
        mock_count = len(mock_ids)

    _validate_about(repo_root, slug)
    return {
        "domains": len(domains),
        "objectives": len(objective_to_domain),
        "lessons": sum(lesson_counts.values()),
        "questions": total_questions,
        "labs": sum(lab_counts.values()),
        "mock_questions": mock_count,
    }


def validate_repo(repo_root: Path = REPO_ROOT) -> dict[str, dict[str, int]]:
    content_root = repo_root / "content"
    if not content_root.is_dir():
        raise ContentValidationError("No existe el directorio content.")
    results: dict[str, dict[str, int]] = {}
    for topic_root in sorted(path for path in content_root.iterdir() if path.is_dir()):
        results[topic_root.name] = validate_topic_tree(repo_root, topic_root.name)
    if not results:
        raise ContentValidationError("No hay temas para validar.")

    if (repo_root / "pyproject.toml").exists():
        required_assets = [
            repo_root / "app/services/topic_transfer/core.py",
            repo_root / "app/api/topic_transfer.py",
            repo_root / "scripts/manage_topic_transfer.py",
            repo_root / "frontend/src/components/TopicTransferPanel.tsx",
            repo_root / "frontend/src/api/topicTransfer.ts",
            repo_root / "tests/test_topic_transfer_contract.py",
        ]
        missing = [str(path) for path in required_assets if not path.is_file()]
        if missing:
            raise ContentValidationError(
                "Faltan activos canónicos de transferencia: " + ", ".join(missing)
            )
        contract = _require_text(repo_root / "tests/test_topic_transfer_contract.py")
        if IMPLEMENTATION_ID != "learn-up-topic-transfer/1" or IMPLEMENTATION_ID not in contract:
            raise ContentValidationError("El contrato de transferencia no coincide.")
        agents_path = repo_root / ".local" / "AGENTS.md"
        agents = _require_text(agents_path) if agents_path.is_file() else ""
        if re.search(r"<(?:app_version|faq_llm_backend)>", agents):
            raise ContentValidationError("AGENTS.md conserva placeholders sin resolver.")
    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    try:
        results = validate_repo()
    except ContentValidationError as exc:
        logging.error("%s", exc)
        raise SystemExit(1) from exc
    for slug, counts in results.items():
        logging.info("%s: %s", slug, counts)
    logging.info("Validación de contenido correcta.")


if __name__ == "__main__":
    main()
