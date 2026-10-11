from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_default_user, get_topic_or_404
from app.badges import BASE_BADGES
from app.db import get_session
from app.models import Badge, UserBadge
from app.schemas import BadgeOut, DashboardOut, ReviewQueueItem
from app.services.progress import build_dashboard, build_review_queue

router = APIRouter(prefix="/api/t/{topic_slug}/progress", tags=["progress"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    topic_slug: str, session: Session = Depends(get_session)
) -> DashboardOut:
    topic = get_topic_or_404(topic_slug, session)
    return build_dashboard(session, topic, get_default_user(session))


@router.get("/review-queue", response_model=list[ReviewQueueItem])
def review_queue(
    topic_slug: str, session: Session = Depends(get_session)
) -> list[ReviewQueueItem]:
    topic = get_topic_or_404(topic_slug, session)
    return build_review_queue(session, topic, get_default_user(session))


@router.get("/badges", response_model=list[BadgeOut])
def badges(
    topic_slug: str, session: Session = Depends(get_session)
) -> list[BadgeOut]:
    get_topic_or_404(topic_slug, session)
    user = get_default_user(session)
    earned = {
        row.badge_id: row.earned_at
        for row in session.execute(
            select(UserBadge).where(UserBadge.user_id == user.id)
        ).scalars()
    }
    return [
        BadgeOut(
            code=badge.code,
            name=badge.name,
            description=badge.description,
            icon=badge.icon,
            earned_at=earned.get(badge.id),
        )
        for badge in session.execute(select(Badge).where(
            Badge.code.in_([item[0] for item in BASE_BADGES]) | Badge.code.like("domain-%")
        ).order_by(Badge.code)).scalars()
    ]
