from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_default_user, get_topic_or_404
from app.content import faq
from app.db import SessionLocal, get_session
from app.models import Domain, Lab, LabAttempt, LabCheck, Objective
from app.schemas import (
    FaqEntryOut,
    LabCheckAnswerOut,
    LabCheckHintOut,
    LabCheckRequest,
    LabCheckResult,
    LabCheckResultItem,
    LabListItem,
    LabOut,
    LabSelfCheckOut,
    QuestionAskRequest,
)
from app.services import labs as lab_service
from app.services import teaching

router = APIRouter(prefix="/api/t/{topic_slug}/labs", tags=["labs"])


def _lab_query(topic_id: int):
    return (
        select(Lab)
        .join(Objective)
        .join(Domain)
        .where(Domain.topic_id == topic_id)
        .options(
            selectinload(Lab.objective).selectinload(Objective.domain),
            selectinload(Lab.checks),
        )
    )


def _get_lab(session: Session, topic_id: int, slug: str) -> Lab:
    lab = session.execute(
        _lab_query(topic_id).where(Lab.slug == slug)
    ).scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Práctica inexistente.")
    return lab


def _passed(session: Session, user_id: int, lab_id: int) -> bool:
    return (
        session.execute(
            select(LabAttempt.id).where(
                LabAttempt.user_id == user_id,
                LabAttempt.lab_id == lab_id,
                LabAttempt.passed.is_(True),
            )
        ).first()
        is not None
    )


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


@router.get("", response_model=list[LabListItem])
def list_labs(
    topic_slug: str, session: Session = Depends(get_session)
) -> list[LabListItem]:
    topic = get_topic_or_404(topic_slug, session)
    if not topic.labs_enabled:
        return []
    user = get_default_user(session)
    labs = session.execute(
        _lab_query(topic.id).order_by(Domain.code, Objective.code, Lab.title)
    ).scalars()
    return [
        LabListItem(
            id=lab.id,
            slug=lab.slug,
            title=lab.title,
            objective_code=lab.objective.code,
            objective_title=lab.objective.title,
            domain_code=lab.objective.domain.code,
            scenario_markdown=lab.scenario_markdown,
            task_markdown=lab.task_markdown,
            self_check_markdown=[
                check.prompt_markdown
                for check in sorted(lab.checks, key=lambda value: value.position)
            ],
            passed=_passed(session, user.id, lab.id),
        )
        for lab in labs
    ]


@router.get("/{slug}", response_model=LabOut)
def get_lab(
    topic_slug: str, slug: str, session: Session = Depends(get_session)
) -> LabOut:
    topic = get_topic_or_404(topic_slug, session)
    user = get_default_user(session)
    lab = _get_lab(session, topic.id, slug)
    return LabOut(
        id=lab.id,
        slug=lab.slug,
        title=lab.title,
        objective_code=lab.objective.code,
        objective_title=lab.objective.title,
        domain_code=lab.objective.domain.code,
        scenario_markdown=lab.scenario_markdown,
        setup_sql=lab.setup_sql,
        task_markdown=lab.task_markdown,
        expected_result=lab.expected_result,
        faq=_faq_out(lab.faq_markdown),
        self_check=[
            LabSelfCheckOut(
                position=check.position,
                prompt_markdown=check.prompt_markdown,
                kind=check.kind,
                hint_available=lab_service.check_hint_available(check),
            )
            for check in sorted(lab.checks, key=lambda value: value.position)
        ],
        passed=_passed(session, user.id, lab.id),
    )


@router.post("/{slug}/check", response_model=LabCheckResult)
def check_lab(
    topic_slug: str,
    slug: str,
    request: LabCheckRequest,
    session: Session = Depends(get_session),
) -> LabCheckResult:
    topic = get_topic_or_404(topic_slug, session)
    user = get_default_user(session)
    lab = _get_lab(session, topic.id, slug)
    checks = sorted(lab.checks, key=lambda value: value.position)
    if len(request.answers) != len(checks):
        raise HTTPException(
            status_code=400, detail="La cantidad de respuestas no coincide."
        )
    results: list[LabCheckResultItem] = []
    for index, check in enumerate(checks):
        previous = request.answers[index - 1] if index > 0 else None
        passed = lab_service.check_answer(check, request.answers[index], previous)
        results.append(
            LabCheckResultItem(
                position=check.position,
                prompt_markdown=check.prompt_markdown,
                passed=passed,
            )
        )
    passed_all = all(result.passed for result in results)
    session.add(
        LabAttempt(user_id=user.id, lab_id=lab.id, passed=passed_all)
    )
    session.commit()
    return LabCheckResult(passed=passed_all, results=results, badges_earned=[])


def _check_at(lab: Lab, position: int) -> LabCheck:
    check = next((item for item in lab.checks if item.position == position), None)
    if check is None:
        raise HTTPException(status_code=404, detail="Autocontrol inexistente.")
    return check


@router.get("/{slug}/self-check/{position}/hint", response_model=LabCheckHintOut)
def check_hint(
    topic_slug: str,
    slug: str,
    position: int,
    session: Session = Depends(get_session),
) -> LabCheckHintOut:
    topic = get_topic_or_404(topic_slug, session)
    check = _check_at(_get_lab(session, topic.id, slug), position)
    try:
        return LabCheckHintOut(
            position=position, hint=lab_service.build_check_hint(check)
        )
    except lab_service.LabCheckError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{slug}/self-check/{position}/answer", response_model=LabCheckAnswerOut)
def check_answer(
    topic_slug: str,
    slug: str,
    position: int,
    session: Session = Depends(get_session),
) -> LabCheckAnswerOut:
    topic = get_topic_or_404(topic_slug, session)
    check = _check_at(_get_lab(session, topic.id, slug), position)
    try:
        return LabCheckAnswerOut(
            position=position, answer=lab_service.build_check_answer(check)
        )
    except lab_service.LabCheckError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{slug}/questions")
def ask_question(
    topic_slug: str,
    slug: str,
    request: QuestionAskRequest,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    topic = get_topic_or_404(topic_slug, session)
    _get_lab(session, topic.id, slug)

    def stream():
        with SessionLocal() as stream_session:
            stream_topic = get_topic_or_404(topic_slug, stream_session)
            lab = _get_lab(stream_session, stream_topic.id, slug)
            try:
                for event in teaching.ask_about_lab(
                    stream_session,
                    lab,
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
    lab = _get_lab(session, topic.id, slug)
    try:
        lab.faq_markdown = faq.remove_faq_entry(lab.faq_markdown, index)
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    faq.sync_lab_yaml_faq(teaching._lab_path(topic_slug, slug), lab.faq_markdown)
    session.commit()
    return Response(status_code=204)
