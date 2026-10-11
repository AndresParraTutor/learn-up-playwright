from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import (
    XP_MOCK_PASS_BONUS,
    XP_PER_CORRECT_ANSWER,
)
from app.models import Badge, Response, User, UserBadge
from app.badges import BASE_BADGES
from app.schemas import BadgeOut



def award_badge(session: Session, user: User, code: str) -> BadgeOut | None:
    if code not in {item[0] for item in BASE_BADGES} and not code.startswith("domain-"):
        return None
    badge = session.execute(select(Badge).where(Badge.code == code)).scalar_one_or_none()
    if badge is None:
        return None
    existing = session.execute(
        select(UserBadge).where(
            UserBadge.user_id == user.id, UserBadge.badge_id == badge.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None
    earned = UserBadge(user_id=user.id, badge_id=badge.id, earned_at=datetime.now(UTC))
    session.add(earned)
    session.flush()
    return BadgeOut(
        code=badge.code,
        name=badge.name,
        description=badge.description,
        icon=badge.icon,
        earned_at=earned.earned_at,
    )


def on_answer(
    session: Session, user: User, correct: bool
) -> tuple[int, list[BadgeOut]]:
    xp = XP_PER_CORRECT_ANSWER if correct else 0
    user.xp += xp
    earned: list[BadgeOut] = []
    response_count = session.scalar(select(func.count(Response.id))) or 0
    if response_count <= 1:
        badge = award_badge(session, user, "first-attempt")
        if badge:
            earned.append(badge)
    return xp, earned


def on_finish(
    session: Session,
    user: User,
    attempt_type: str,
    score_raw: int,
    total: int,
    passed: bool | None,
) -> tuple[int, list[BadgeOut]]:
    xp = 0
    earned: list[BadgeOut] = []
    if attempt_type != "mock" and total > 0 and score_raw == total:
        badge = award_badge(session, user, "clean-sweep")
        if badge:
            earned.append(badge)
    if attempt_type == "mock" and passed:
        xp = XP_MOCK_PASS_BONUS
        user.xp += xp
    return xp, earned
