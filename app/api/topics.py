from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_default_user, get_topic_or_404
from app.db import get_session
from app.models import Domain, Objective, Topic
from app.schemas import TopicOut, TopicSummaryOut
from app.services.progress import build_dashboard

router = APIRouter(prefix="/api/topics", tags=["topics"])


def _topic_out(topic: Topic) -> TopicOut:
    return TopicOut(
        id=topic.id,
        slug=topic.slug,
        name=topic.name,
        description=topic.description,
        syllabus_version=topic.syllabus_version,
        assessment_enabled=topic.assessment_enabled,
        assessment_question_count=topic.assessment_question_count,
        assessment_minutes=topic.assessment_minutes,
        assessment_scoring=topic.assessment_scoring,
        pass_pct=topic.pass_pct,
        pass_score_scaled=topic.pass_score_scaled,
        max_score_scaled=topic.max_score_scaled,
        penalty_for_wrong_answers=topic.penalty_for_wrong_answers,
        labs_enabled=topic.labs_enabled,
        strategy_enabled=topic.strategy_enabled,
    )


@router.get("", response_model=list[TopicSummaryOut])
def list_topics(session: Session = Depends(get_session)) -> list[TopicSummaryOut]:
    user = get_default_user(session)
    result: list[TopicSummaryOut] = []
    for topic in session.execute(select(Topic).order_by(Topic.name)).scalars():
        domain_count = session.scalar(
            select(func.count(Domain.id)).where(Domain.topic_id == topic.id)
        ) or 0
        objective_count = session.scalar(
            select(func.count(Objective.id))
            .join(Domain)
            .where(Domain.topic_id == topic.id)
        ) or 0
        dashboard = build_dashboard(session, topic, user)
        result.append(
            TopicSummaryOut(
                slug=topic.slug,
                name=topic.name,
                description=topic.description,
                syllabus_version=topic.syllabus_version,
                domain_count=domain_count,
                objective_count=objective_count,
                overall_ready_pct=dashboard.overall_ready_pct,
            )
        )
    return result


@router.get("/{slug}", response_model=TopicOut)
def get_topic(slug: str, session: Session = Depends(get_session)) -> TopicOut:
    return _topic_out(get_topic_or_404(slug, session))
