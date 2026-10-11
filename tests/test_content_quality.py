from __future__ import annotations

from pathlib import Path
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.content.seed import seed_topic
from app.content.validate import validate_topic_tree
from app.models import Badge, Base, Domain, Mastery, Objective, Topic, User, UserBadge
from app.api.progress import badges
from app.services.gamification import award_badge, on_answer, on_finish
from app.services.attempts import AttemptError, create_attempt
from app.services.progress import build_dashboard


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_playwright_content_tree_is_complete_and_valid() -> None:
    assert validate_topic_tree(REPO_ROOT, "playwright") == {
        "domains": 7,
        "objectives": 25,
        "lessons": 25,
        "questions": 75,
        "labs": 25,
        "mock_questions": 0,
    }


def test_playwright_keeps_module_practice_without_mock_requirement(tmp_path: Path) -> None:
    engine = create_engine(f"duckdb:///{(tmp_path / 'student.duckdb').as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA learn"))
        Base.metadata.create_all(engine)
        with Session(engine, expire_on_commit=False) as session:
            seed_topic(session, REPO_ROOT / "content" / "playwright")
            user = User(display_name="Estudiante")
            session.add(user)
            session.commit()
            topic = session.execute(select(Topic)).scalar_one()
            assert topic.assessment_enabled is False
            with pytest.raises(AttemptError, match="no tiene evaluación final"):
                create_attempt(session, topic, user, "mock")
            for domain in topic.domains:
                attempt = create_attempt(
                    session, topic, user, "domain_drill", domain_code=domain.code
                )
                assert attempt.questions
                assert all(
                    item.question.objective.domain_id == domain.id
                    for item in attempt.questions
                )
            assert create_attempt(session, topic, user, "quick_drill").questions
            assert build_dashboard(session, topic, user).exam_ready is False
            objectives = session.execute(
                select(Objective).join(Domain).where(Domain.topic_id == topic.id)
            ).scalars()
            for objective in objectives:
                session.add(
                    Mastery(
                        user_id=user.id,
                        objective_id=objective.id,
                        repetitions=2,
                        ease_factor=2.5,
                    )
                )
            session.commit()
            dashboard = build_dashboard(session, topic, user)
            assert dashboard.overall_ready_pct == 80
            assert dashboard.exam_ready is True
            user.current_streak = 7
            user.longest_streak = 12
            user.streak_freeze_count = 2
            user.last_activity_date = date.today() - timedelta(days=3)
            retired_codes = {"streak-3", "streak-7", "mock-pass", "exam-ready"}
            for code in retired_codes:
                badge = Badge(code=code, name="Legacy", description="Legacy", icon="")
                session.add(badge)
                session.flush()
                session.add(UserBadge(user_id=user.id, badge_id=badge.id))
            session.commit()
            xp_before = user.xp
            xp, earned = on_answer(session, user, True)
            assert xp == 10 and user.xp == xp_before + 10
            assert (user.current_streak, user.longest_streak, user.streak_freeze_count) == (7, 12, 2)
            assert user.last_activity_date == date.today() - timedelta(days=3)
            assert all(not item.code.startswith("streak-") for item in earned)
            visible_codes = {item.code for item in badges("playwright", session)}
            assert visible_codes.isdisjoint(retired_codes)
            assert {"first-attempt", "clean-sweep"}.issubset(visible_codes)
            assert len(visible_codes) == 9
            for code in retired_codes:
                assert award_badge(session, user, code) is None
            assert on_finish(session, user, "mock", 50, 50, True)[1] == []
            assert [item.code for item in on_finish(session, user, "domain_drill", 10, 10, None)[1]] == ["clean-sweep"]
            assert not any("streak" in key for key in dashboard.model_dump())
    finally:
        engine.dispose()
