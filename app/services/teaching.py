from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.orm import Session

from app.content import faq
from app.models import Lab, Lesson
from app.services import lesson_qa

REPO_ROOT = Path(__file__).resolve().parents[2]


def _lesson_path(topic_slug: str, slug: str) -> Path:
    matches = list(
        (REPO_ROOT / "content" / topic_slug / "lessons").rglob(f"{slug}.md")
    )
    if len(matches) != 1:
        raise lesson_qa.LessonQAError("No se encontró un único archivo de lección.")
    return matches[0]


def _lab_path(topic_slug: str, slug: str) -> Path:
    matches = list((REPO_ROOT / "content" / topic_slug / "labs").rglob(f"{slug}.yaml"))
    if len(matches) != 1:
        raise lesson_qa.LessonQAError("No se encontró un único archivo de práctica.")
    return matches[0]


def _wire_events(
    events,
    current_faq: str,
    selected_text: str,
) -> Iterator[dict]:
    index = len(faq.parse_faq_entries(current_faq)) if current_faq.strip() else 0
    for event in events:
        if event["type"] == "delta":
            yield {"type": "delta", "delta": event["text"]}
        elif event["type"] == "insufficient":
            yield {"type": "insufficient"}
        else:
            yield {
                "type": "result",
                "index": index,
                "question": event["title"],
                "selected_text": selected_text,
                "answer_markdown": event["answer"],
            }


def ask_about_lesson(
    session: Session,
    lesson: Lesson,
    topic_slug: str,
    selected_text: str,
    question: str,
    use_full_sources: bool = False,
) -> Iterator[dict]:
    context = (
        lesson.body_markdown
        + "\n\n## Why It Matters\n\n"
        + lesson.why_it_matters_markdown
    )
    if use_full_sources:
        context += "\n\n" + lesson_qa.topic_sources_markdown(topic_slug)
    events = lesson_qa.ask(
        context,
        selected_text,
        question,
        allow_insufficient=not use_full_sources,
    )
    for event in _wire_events(events, lesson.faq_markdown, selected_text):
        if event["type"] == "result":
            lesson.faq_markdown = faq.append_faq_entry(
                lesson.faq_markdown,
                event["question"],
                selected_text,
                event["answer_markdown"],
            )
            faq.sync_markdown_faq_section(
                _lesson_path(topic_slug, lesson.slug), lesson.faq_markdown
            )
            session.commit()
        yield event


def ask_about_lab(
    session: Session,
    lab: Lab,
    topic_slug: str,
    selected_text: str,
    question: str,
    use_full_sources: bool = False,
) -> Iterator[dict]:
    context = (
        "## Escenario\n\n"
        + lab.scenario_markdown
        + "\n\n## Tarea\n\n"
        + lab.task_markdown
    )
    if use_full_sources:
        context += "\n\n" + lesson_qa.topic_sources_markdown(topic_slug)
    events = lesson_qa.ask(
        context,
        selected_text,
        question,
        allow_insufficient=not use_full_sources,
    )
    for event in _wire_events(events, lab.faq_markdown, selected_text):
        if event["type"] == "result":
            lab.faq_markdown = faq.append_faq_entry(
                lab.faq_markdown,
                event["question"],
                selected_text,
                event["answer_markdown"],
            )
            faq.sync_lab_yaml_faq(_lab_path(topic_slug, lab.slug), lab.faq_markdown)
            session.commit()
        yield event
