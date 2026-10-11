from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_topic_or_404
from app.content import faq
from app.db import SessionLocal, get_session
from app.models import Domain, Lesson, Objective
from app.schemas import (
    FaqEntryOut,
    LessonListItem,
    LessonOut,
    QuestionAskRequest,
    VideoStatusOut,
)
from app.services import lesson_video, teaching
from app.services.lesson_qa import LessonQAError

router = APIRouter(prefix="/api/t/{topic_slug}/lessons", tags=["lessons"])


def _lesson_query(topic_id: int):
    return (
        select(Lesson)
        .join(Objective)
        .join(Domain)
        .where(Domain.topic_id == topic_id)
        .options(selectinload(Lesson.objective).selectinload(Objective.domain))
    )


def _get_lesson_by_slug(session: Session, topic_id: int, slug: str) -> Lesson:
    lesson = session.execute(
        _lesson_query(topic_id).where(Lesson.slug == slug)
    ).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lección inexistente.")
    return lesson


def _faq_out(markdown: str) -> list[FaqEntryOut]:
    entries = faq.parse_faq_entries(markdown) if markdown.strip() else []
    return [
        FaqEntryOut(
            index=index,
            question=title,
            selected_text=selected,
            answer_markdown=answer,
        )
        for index, (title, selected, answer) in enumerate(entries)
    ]


def _lesson_list_item(lesson: Lesson, topic_slug: str) -> LessonListItem:
    status = (
        "done"
        if "[placeholder]" not in lesson.body_markdown
        else lesson_video.get_job_status(topic_slug, lesson.slug)["status"]
    )
    return LessonListItem(
        id=lesson.id,
        slug=lesson.slug,
        title=lesson.title,
        objective_code=lesson.objective.code,
        objective_title=lesson.objective.title,
        domain_code=lesson.objective.domain.code,
        domain_name=lesson.objective.domain.name,
        body_markdown=lesson.body_markdown,
        why_it_matters_markdown=lesson.why_it_matters_markdown,
        video_status=status,
    )


def _lesson_out(lesson: Lesson) -> LessonOut:
    return LessonOut(
        id=lesson.id,
        slug=lesson.slug,
        title=lesson.title,
        objective_code=lesson.objective.code,
        objective_title=lesson.objective.title,
        domain_code=lesson.objective.domain.code,
        domain_name=lesson.objective.domain.name,
        body_markdown=lesson.body_markdown,
        why_it_matters_markdown=lesson.why_it_matters_markdown,
        faq=_faq_out(lesson.faq_markdown),
    )


@router.get("", response_model=list[LessonListItem])
def list_lessons(
    topic_slug: str, session: Session = Depends(get_session)
) -> list[LessonListItem]:
    topic = get_topic_or_404(topic_slug, session)
    lessons = session.execute(
        _lesson_query(topic.id).order_by(Domain.code, Objective.code, Lesson.title)
    ).scalars()
    return [_lesson_list_item(lesson, topic_slug) for lesson in lessons]


@router.get("/objective/{code}", response_model=list[LessonListItem])
def list_lessons_for_objective(
    topic_slug: str, code: str, session: Session = Depends(get_session)
) -> list[LessonListItem]:
    topic = get_topic_or_404(topic_slug, session)
    lessons = session.execute(
        _lesson_query(topic.id)
        .where(Objective.code == code)
        .order_by(Lesson.title)
    ).scalars()
    return [_lesson_list_item(lesson, topic_slug) for lesson in lessons]


@router.get("/{slug}", response_model=LessonOut)
def get_lesson(
    topic_slug: str, slug: str, session: Session = Depends(get_session)
) -> LessonOut:
    topic = get_topic_or_404(topic_slug, session)
    return _lesson_out(_get_lesson_by_slug(session, topic.id, slug))


@router.post("/{slug}/questions")
def ask_question(
    topic_slug: str,
    slug: str,
    request: QuestionAskRequest,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    topic = get_topic_or_404(topic_slug, session)
    _get_lesson_by_slug(session, topic.id, slug)

    def stream():
        with SessionLocal() as stream_session:
            stream_topic = get_topic_or_404(topic_slug, stream_session)
            lesson = _get_lesson_by_slug(stream_session, stream_topic.id, slug)
            try:
                for event in teaching.ask_about_lesson(
                    stream_session,
                    lesson,
                    topic_slug,
                    request.selected_text,
                    request.question,
                    request.use_full_sources,
                ):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as exc:
                stream_session.rollback()
                payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
                yield f"event: error\ndata: {payload}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.delete("/{slug}/faq/{index}", status_code=204)
def delete_faq(
    topic_slug: str,
    slug: str,
    index: int,
    session: Session = Depends(get_session),
) -> Response:
    topic = get_topic_or_404(topic_slug, session)
    lesson = _get_lesson_by_slug(session, topic.id, slug)
    try:
        lesson.faq_markdown = faq.remove_faq_entry(lesson.faq_markdown, index)
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    faq.sync_markdown_faq_section(
        teaching._lesson_path(topic_slug, slug), lesson.faq_markdown
    )
    session.commit()
    return Response(status_code=204)


@router.post("/{slug}/video/generate", response_model=VideoStatusOut)
def trigger_lesson_video_generation(
    topic_slug: str, slug: str, session: Session = Depends(get_session)
) -> VideoStatusOut:
    topic = get_topic_or_404(topic_slug, session)
    lesson = _get_lesson_by_slug(session, topic.id, slug)
    try:
        lesson_video.start_generation(topic_slug, lesson.slug)
    except lesson_video.LessonVideoError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return VideoStatusOut(status="running")


@router.get("/{slug}/video/status", response_model=VideoStatusOut)
def get_lesson_video_status(
    topic_slug: str, slug: str, session: Session = Depends(get_session)
) -> VideoStatusOut:
    topic = get_topic_or_404(topic_slug, session)
    lesson = _get_lesson_by_slug(session, topic.id, slug)
    return VideoStatusOut(**lesson_video.get_job_status(topic_slug, lesson.slug))
