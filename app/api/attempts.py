from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_default_user, get_topic_or_404
from app.db import get_session
from app.schemas import (
    AttemptCreate,
    AttemptFinishOut,
    AttemptOut,
    AttemptReviewOut,
    ResponseCreate,
    ResponseResult,
)
from app.services import attempts

router = APIRouter(prefix="/api/t/{topic_slug}/attempts", tags=["attempts"])


@router.post("", response_model=AttemptOut)
def create_attempt(
    topic_slug: str,
    request: AttemptCreate,
    session: Session = Depends(get_session),
) -> AttemptOut:
    topic = get_topic_or_404(topic_slug, session)
    user = get_default_user(session)
    try:
        attempt = attempts.create_attempt(
            session,
            topic,
            user,
            request.attempt_type,
            request.domain_code,
            request.objective_code,
            request.question_count,
        )
    except attempts.AttemptError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return attempts.attempt_out(attempt)


@router.get("/{attempt_id}", response_model=AttemptOut)
def get_attempt(
    topic_slug: str,
    attempt_id: int,
    session: Session = Depends(get_session),
) -> AttemptOut:
    topic = get_topic_or_404(topic_slug, session)
    try:
        attempt = attempts.get_attempt(session, attempt_id, topic.id)
    except attempts.AttemptError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return attempts.attempt_out(attempt)


@router.post("/{attempt_id}/responses", response_model=ResponseResult)
def submit_response(
    topic_slug: str,
    attempt_id: int,
    request: ResponseCreate,
    session: Session = Depends(get_session),
) -> ResponseResult:
    topic = get_topic_or_404(topic_slug, session)
    user = get_default_user(session)
    try:
        attempt = attempts.get_attempt(session, attempt_id, topic.id)
        return attempts.submit_response(
            session,
            attempt,
            user,
            request.question_id,
            request.selected_choice_ids,
        )
    except attempts.AttemptError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{attempt_id}/finish", response_model=AttemptFinishOut)
def finish_attempt(
    topic_slug: str,
    attempt_id: int,
    session: Session = Depends(get_session),
) -> AttemptFinishOut:
    topic = get_topic_or_404(topic_slug, session)
    user = get_default_user(session)
    try:
        attempt = attempts.get_attempt(session, attempt_id, topic.id)
        return attempts.finish_attempt(session, attempt, user)
    except attempts.AttemptError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{attempt_id}/review", response_model=AttemptReviewOut)
def review_attempt(
    topic_slug: str,
    attempt_id: int,
    session: Session = Depends(get_session),
) -> AttemptReviewOut:
    topic = get_topic_or_404(topic_slug, session)
    try:
        attempt = attempts.get_attempt(session, attempt_id, topic.id)
        return attempts.review_out(attempt)
    except attempts.AttemptError as exc:
        status = 409 if "todavía no terminó" in str(exc) else 404
        detail: str | dict[str, str] = str(exc)
        if status == 409:
            detail = {"code": "attempt_not_finished", "message": str(exc)}
        raise HTTPException(status_code=status, detail=detail) from exc
