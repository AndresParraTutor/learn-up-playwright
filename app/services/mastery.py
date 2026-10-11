from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import (
    MASTERY_MIN_EASE_FACTOR,
    MASTERY_MIN_REPETITIONS,
    SM2_MAX_INTERVAL_DAYS,
    SM2_MIN_EASE_FACTOR,
    SM2_QUALITY_CORRECT,
    SM2_QUALITY_INCORRECT,
)
from app.models import Mastery


def apply_mastery(
    session: Session, user_id: int, objective_id: int, correct: bool
) -> Mastery:
    mastery = session.execute(
        select(Mastery).where(
            Mastery.user_id == user_id, Mastery.objective_id == objective_id
        )
    ).scalar_one_or_none()
    if mastery is None:
        mastery = Mastery(user_id=user_id, objective_id=objective_id)
        session.add(mastery)
        session.flush()
    quality = SM2_QUALITY_CORRECT if correct else SM2_QUALITY_INCORRECT
    today = datetime.now().date()
    ease = float(mastery.ease_factor)
    if quality < 3:
        mastery.repetitions = 0
        mastery.interval_days = 1
    else:
        if mastery.repetitions == 0:
            mastery.interval_days = 1
        elif mastery.repetitions == 1:
            mastery.interval_days = 6
        else:
            mastery.interval_days = min(
                round(mastery.interval_days * ease), SM2_MAX_INTERVAL_DAYS
            )
        mastery.repetitions += 1
    ease += 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    mastery.ease_factor = Decimal(str(round(max(SM2_MIN_EASE_FACTOR, ease), 2)))
    mastery.due_on = today + timedelta(days=mastery.interval_days)
    mastery.last_reviewed_at = datetime.now(UTC)
    return mastery


def is_mastered(mastery: Mastery | None) -> bool:
    return bool(
        mastery is not None
        and mastery.repetitions >= MASTERY_MIN_REPETITIONS
        and float(mastery.ease_factor) >= MASTERY_MIN_EASE_FACTOR
    )
