from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.constants import (
    ATTEMPT_HISTORY_LIMIT,
    DOMAIN_READINESS_WEIGHT_PCT,
    LABS_READINESS_WEIGHT_PCT,
    READY_THRESHOLD_PCT,
    STRATEGY_READINESS_WEIGHT_PCT,
    STUDY_OBJECTIVES_PER_WEEK,
)
from app.models import (
    Attempt,
    AttemptQuestion,
    Domain,
    Lab,
    LabAttempt,
    Mastery,
    Objective,
    StrategyLesson,
    StrategyLessonProgress,
    Topic,
    User,
)
from app.schemas import (
    AttemptSummary,
    DashboardOut,
    DomainReadiness,
    ReviewQueueItem,
    StudyPlanItem,
)
from app.services.mastery import is_mastered


def build_review_queue(
    session: Session, topic: Topic, user: User
) -> list[ReviewQueueItem]:
    today = datetime.now().date()
    objectives = session.execute(
        select(Objective)
        .join(Domain)
        .where(Domain.topic_id == topic.id)
        .order_by(Domain.code, Objective.code)
    ).scalars().all()
    mastery_by_objective = {
        mastery.objective_id: mastery
        for mastery in session.execute(
            select(Mastery).where(Mastery.user_id == user.id)
        ).scalars()
    }
    items: list[ReviewQueueItem] = []
    priority = {"weak": 0, "due": 1, "new": 2}
    for objective in objectives:
        mastery = mastery_by_objective.get(objective.id)
        if mastery is None:
            status = "new"
        elif not is_mastered(mastery):
            status = "weak"
        elif mastery.due_on is not None and mastery.due_on <= today:
            status = "due"
        else:
            continue
        items.append(
            ReviewQueueItem(
                objective_code=objective.code,
                objective_title=objective.title,
                status=status,
            )
        )
    return sorted(items, key=lambda item: (priority[item.status], item.objective_code))


def build_dashboard(session: Session, topic: Topic, user: User) -> DashboardOut:
    domains = session.execute(
        select(Domain)
        .where(Domain.topic_id == topic.id)
        .options(selectinload(Domain.objectives))
        .order_by(Domain.code)
    ).scalars().all()
    masteries = {
        mastery.objective_id: mastery
        for mastery in session.execute(
            select(Mastery).where(Mastery.user_id == user.id)
        ).scalars()
    }
    domain_rows: list[DomainReadiness] = []
    weighted_sum = 0
    total_weight = 0
    objectives_in_order: list[Objective] = []
    for domain in domains:
        objectives = sorted(domain.objectives, key=lambda value: value.code)
        objectives_in_order.extend(objectives)
        mastered = sum(
            1 for objective in objectives if is_mastered(masteries.get(objective.id))
        )
        ready = round(100 * mastered / len(objectives)) if objectives else 0
        domain_rows.append(
            DomainReadiness(
                code=domain.code,
                name=domain.name,
                weight_pct=domain.weight_pct,
                ready_pct=ready,
            )
        )
        weighted_sum += ready * domain.weight_pct
        total_weight += domain.weight_pct
    domain_ready_pct = round(weighted_sum / total_weight) if total_weight else 0

    lab_total = session.scalar(
        select(func.count(Lab.id))
        .join(Objective)
        .join(Domain)
        .where(Domain.topic_id == topic.id)
    ) or 0
    passed_lab_ids = {
        value
        for value in session.execute(
            select(LabAttempt.lab_id)
            .join(Lab)
            .join(Objective)
            .join(Domain)
            .where(
                Domain.topic_id == topic.id,
                LabAttempt.user_id == user.id,
                LabAttempt.passed.is_(True),
            )
        ).scalars()
    }
    labs_pct = round(100 * len(passed_lab_ids) / lab_total) if lab_total else 0

    strategy_total = session.scalar(
        select(func.count(StrategyLesson.id)).where(StrategyLesson.topic_id == topic.id)
    ) or 0
    strategy_read = session.scalar(
        select(func.count(StrategyLessonProgress.id))
        .join(StrategyLesson)
        .where(
            StrategyLesson.topic_id == topic.id,
            StrategyLessonProgress.user_id == user.id,
        )
    ) or 0
    strategy_pct = (
        round(100 * strategy_read / strategy_total) if strategy_total else 0
    )

    domain_weight = DOMAIN_READINESS_WEIGHT_PCT
    components: list[tuple[int, int]] = []
    if topic.labs_enabled:
        components.append((labs_pct, LABS_READINESS_WEIGHT_PCT))
    else:
        domain_weight += LABS_READINESS_WEIGHT_PCT
    if topic.strategy_enabled:
        components.append((strategy_pct, STRATEGY_READINESS_WEIGHT_PCT))
    else:
        domain_weight += STRATEGY_READINESS_WEIGHT_PCT
    overall = round(
        (domain_ready_pct * domain_weight + sum(value * weight for value, weight in components))
        / 100
    )

    last_mock = session.execute(
        select(Attempt)
        .where(
            Attempt.user_id == user.id,
            Attempt.topic_id == topic.id,
            Attempt.attempt_type == "mock",
            Attempt.finished_at.is_not(None),
        )
        .order_by(Attempt.finished_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    exam_ready = overall >= READY_THRESHOLD_PCT and (
        not topic.assessment_enabled or bool(last_mock and last_mock.passed)
    )

    attempts = list(
        session.execute(
            select(Attempt)
            .where(Attempt.user_id == user.id, Attempt.topic_id == topic.id)
            .options(selectinload(Attempt.questions))
            .order_by(Attempt.started_at.desc())
            .limit(ATTEMPT_HISTORY_LIMIT)
        ).scalars()
    )
    history = [
        AttemptSummary(
            id=attempt.id,
            attempt_type=attempt.attempt_type,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            score_raw=attempt.score_raw,
            score_scaled=attempt.score_scaled,
            passed=attempt.passed,
            total_questions=len(attempt.questions),
        )
        for attempt in attempts
    ]
    study_plan = [
        StudyPlanItem(
            objective_code=objective.code,
            objective_title=objective.title,
            estimated_week=index // STUDY_OBJECTIVES_PER_WEEK + 1,
        )
        for index, objective in enumerate(objectives_in_order)
    ]
    return DashboardOut(
        domain_readiness=domain_rows,
        domain_ready_pct=domain_ready_pct,
        labs_pct=labs_pct,
        strategy_pct=strategy_pct,
        overall_ready_pct=overall,
        exam_ready=exam_ready,
        xp=user.xp,
        review_queue=build_review_queue(session, topic, user),
        attempt_history=history,
        study_plan=study_plan,
    )
