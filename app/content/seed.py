from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.badges import BASE_BADGES
from app.content import faq
from app.db import SessionLocal, engine
from app.models import (
    Base,
    Badge,
    Choice,
    Domain,
    Lab,
    LabCheck,
    Lesson,
    MockExam,
    MockExamQuestion,
    Objective,
    Question,
    Topic,
    User,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = REPO_ROOT / "content"


class SeedError(RuntimeError):
    pass


def load_lesson_file(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if match is None:
        raise SeedError(f"Frontmatter inválido en {path}")
    frontmatter = yaml.safe_load(match.group(1))
    if not isinstance(frontmatter, dict):
        raise SeedError(f"Frontmatter inválido en {path}")
    return frontmatter, match.group(2).strip()


def split_why_it_matters(body: str) -> tuple[str, str]:
    authored = body.split(faq.FAQ_SECTION_MARKER, 1)[0].rstrip()
    marker = "\n## Why It Matters\n"
    if authored.count(marker) != 1:
        raise SeedError("Cada lección debe contener exactamente un encabezado ## Why It Matters.")
    main, why = authored.split(marker, 1)
    return main.strip(), why.strip()


def _load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SeedError(f"No se pudo leer {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SeedError(f"{path} debe contener un objeto YAML.")
    return data


def _one(session: Session, model: type, **filters):
    return session.execute(select(model).filter_by(**filters)).scalar_one_or_none()


def _topic_values(syllabus: dict) -> dict:
    assessment = syllabus["assessment"]
    modules = syllabus["modules"]
    return {
        "name": str(syllabus["topic_name"]),
        "description": str(syllabus["objective_summary"]).strip(),
        "syllabus_version": str(syllabus["syllabus_version"]),
        "assessment_enabled": bool(assessment["enabled"]),
        "assessment_question_count": int(assessment["question_count"]),
        "assessment_minutes": int(assessment["minutes"]),
        "assessment_scoring": str(assessment["scoring"]),
        "pass_pct": assessment.get("pass_pct"),
        "pass_score_scaled": assessment.get("pass_score_scaled"),
        "max_score_scaled": assessment.get("max_score_scaled"),
        "penalty_for_wrong_answers": bool(assessment["penalty_for_wrong_answers"]),
        "labs_enabled": bool(modules["labs"]),
        "strategy_enabled": bool(modules["strategy"]),
    }


def _upsert_topic(session: Session, slug: str, syllabus: dict) -> Topic:
    topic = _one(session, Topic, slug=slug)
    if topic is None:
        topic = Topic(slug=slug, **_topic_values(syllabus))
        session.add(topic)
    else:
        for key, value in _topic_values(syllabus).items():
            setattr(topic, key, value)
    session.flush()
    return topic


def _seed_taxonomy(
    session: Session, topic: Topic, syllabus: dict
) -> dict[str, Objective]:
    objectives: dict[str, Objective] = {}
    version = str(syllabus["syllabus_version"])
    for domain_data in syllabus["domains"]:
        code = str(domain_data["code"])
        domain = _one(session, Domain, topic_id=topic.id, code=code)
        if domain is None:
            domain = Domain(topic_id=topic.id, code=code)
            session.add(domain)
        domain.name = str(domain_data["name"])
        domain.weight_pct = int(domain_data["weight_pct"])
        domain.syllabus_version = version
        session.flush()
        for objective_data in domain_data["objectives"]:
            objective_code = str(objective_data["code"])
            objective = _one(
                session, Objective, domain_id=domain.id, code=objective_code
            )
            if objective is None:
                objective = Objective(domain_id=domain.id, code=objective_code)
                session.add(objective)
            objective.title = str(objective_data["title"])
            objective.description = "\n".join(
                str(item) for item in objective_data.get("topics", [])
            )
            objective.syllabus_version = version
            session.flush()
            objectives[objective_code] = objective
    return objectives


def _seed_lessons(
    session: Session, topic_root: Path, objectives: dict[str, Objective]
) -> None:
    for path in sorted((topic_root / "lessons").glob("*/*.md")):
        frontmatter, body = load_lesson_file(path)
        code = str(frontmatter["objective"])
        if code not in objectives:
            raise SeedError(f"Objetivo de lección desconocido {code} en {path}")
        main, why = split_why_it_matters(body)
        lesson = _one(session, Lesson, slug=path.stem)
        if lesson is None:
            lesson = Lesson(objective_id=objectives[code].id, slug=path.stem)
            session.add(lesson)
        lesson.objective_id = objectives[code].id
        lesson.title = str(frontmatter["title"])
        lesson.body_markdown = main
        lesson.why_it_matters_markdown = why
        mirrored_faq = faq.faq_from_lesson_text(body)
        if mirrored_faq:
            faq.parse_faq_entries(mirrored_faq)
            lesson.faq_markdown = mirrored_faq


def _seed_questions(
    session: Session,
    topic_root: Path,
    objectives: dict[str, Objective],
    syllabus_version: str,
) -> dict[str, Question]:
    questions: dict[str, Question] = {}
    for path in sorted((topic_root / "questions").glob("*.yaml")):
        data = _load_yaml(path)
        code = str(data["objective"])
        if code not in objectives:
            raise SeedError(f"Objetivo de pregunta desconocido {code} en {path}")
        for question_data in data["questions"]:
            external_id = str(question_data["external_id"])
            question = _one(session, Question, external_id=external_id)
            if question is None:
                question = Question(
                    objective_id=objectives[code].id, external_id=external_id
                )
                session.add(question)
            question.objective_id = objectives[code].id
            question.question_type = str(question_data["type"])
            question.stem_markdown = str(question_data["stem"]).strip()
            question.explanation_markdown = str(question_data["explanation"]).strip()
            question.difficulty = int(question_data["difficulty"])
            question.is_mock_eligible = bool(question_data["is_mock_eligible"])
            question.syllabus_version = syllabus_version
            session.flush()
            for position, choice_data in enumerate(question_data["choices"]):
                choice = _one(
                    session, Choice, question_id=question.id, position=position
                )
                if choice is None:
                    choice = Choice(question_id=question.id, position=position)
                    session.add(choice)
                choice.text_markdown = str(choice_data["text"])
                choice.is_correct = bool(choice_data["correct"])
                choice.distractor_explanation_markdown = str(
                    choice_data["explanation"]
                ).strip()
            questions[external_id] = question
    session.flush()
    return questions


def _seed_labs(
    session: Session, topic_root: Path, objectives: dict[str, Objective]
) -> None:
    for path in sorted((topic_root / "labs").glob("*/*.yaml")):
        data = _load_yaml(path)
        code = str(data["objective"])
        if code not in objectives:
            raise SeedError(f"Objetivo de laboratorio desconocido {code} en {path}")
        lab = _one(session, Lab, slug=path.stem)
        if lab is None:
            lab = Lab(objective_id=objectives[code].id, slug=path.stem)
            session.add(lab)
        lab.objective_id = objectives[code].id
        lab.title = str(data["title"])
        lab.scenario_markdown = str(data["scenario"]).strip()
        lab.setup_sql = str(data["setup_sql"]).strip()
        lab.task_markdown = str(data["task"]).strip()
        lab.expected_result = str(data["expected_result"]).strip()
        mirrored_faq = faq.faq_from_lab_data(data)
        if mirrored_faq:
            lab.faq_markdown = mirrored_faq
        session.flush()
        for position, check_data in enumerate(data["self_check"]):
            check = _one(session, LabCheck, lab_id=lab.id, position=position)
            if check is None:
                check = LabCheck(lab_id=lab.id, position=position)
                session.add(check)
            check.prompt_markdown = str(check_data["prompt"])
            check.kind = str(check_data["kind"])
            value = check_data.get("value")
            check.expected_value = None if value is None else str(value)
            check.case_sensitive = bool(check_data.get("case_sensitive", False))


def _seed_mock(
    session: Session,
    topic: Topic,
    topic_root: Path,
    questions: dict[str, Question],
) -> None:
    for path in sorted((topic_root / "mocks").glob("*.yaml")):
        data = _load_yaml(path)
        code = str(data["code"])
        mock = _one(session, MockExam, topic_id=topic.id, code=code)
        if mock is None:
            mock = MockExam(topic_id=topic.id, code=code)
            session.add(mock)
        mock.syllabus_version = str(data["syllabus_version"])
        session.flush()
        for position, external_id in enumerate(data["questions"]):
            key = str(external_id)
            if key not in questions:
                raise SeedError(f"Pregunta inexistente {key} en {path}")
            item = _one(
                session,
                MockExamQuestion,
                mock_exam_id=mock.id,
                position=position,
            )
            if item is None:
                item = MockExamQuestion(mock_exam_id=mock.id, position=position)
                session.add(item)
            item.question_id = questions[key].id


def _seed_badges(session: Session, topic: Topic) -> None:
    catalog = list(BASE_BADGES)
    for domain in topic.domains:
        catalog.append(
            (
                f"domain-master-{topic.slug}-{domain.code}",
                f"Dominio {domain.code} dominado",
                f"Dominaste todos los objetivos de {domain.name}.",
                "📐",
            )
        )
    for code, name, description, icon in catalog:
        badge = _one(session, Badge, code=code)
        if badge is None:
            badge = Badge(code=code)
            session.add(badge)
        badge.name = name
        badge.description = description
        badge.icon = icon


def seed_topic(session: Session, topic_root: Path) -> None:
    slug = topic_root.name
    syllabus = _load_yaml(topic_root / "syllabus.yaml")
    if str(syllabus.get("topic_slug")) != slug:
        raise SeedError(f"El slug del syllabus no coincide con {topic_root}")
    if sum(int(domain["weight_pct"]) for domain in syllabus["domains"]) != 100:
        raise SeedError(f"Los pesos de {slug} no suman 100.")
    topic = _upsert_topic(session, slug, syllabus)
    objectives = _seed_taxonomy(session, topic, syllabus)
    _seed_lessons(session, topic_root, objectives)
    questions = _seed_questions(
        session, topic_root, objectives, str(syllabus["syllabus_version"])
    )
    if topic.labs_enabled:
        _seed_labs(session, topic_root, objectives)
    if topic.assessment_enabled:
        _seed_mock(session, topic, topic_root, questions)
    session.flush()
    session.refresh(topic, attribute_names=["domains"])
    _seed_badges(session, topic)


def seed_all(content_root: Path = CONTENT_ROOT) -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if _one(session, User, display_name="Estudiante") is None:
            session.add(User(display_name="Estudiante"))
        for topic_root in sorted(path for path in content_root.iterdir() if path.is_dir()):
            seed_topic(session, topic_root)
        session.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    seed_all()
    logging.info("Contenido sembrado correctamente.")


if __name__ == "__main__":
    main()
