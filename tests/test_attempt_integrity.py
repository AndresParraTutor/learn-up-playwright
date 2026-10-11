from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.models import Attempt, Topic, User
from app.services.attempts import AttemptError, attempt_out, review_out, submit_response


def mock_attempt(*, finished: bool = False, started_at: datetime | None = None) -> Attempt:
    topic = Topic(
        slug="playwright",
        name="Playwright",
        description="Curso",
        syllabus_version="v1",
        assessment_enabled=True,
        assessment_question_count=50,
        assessment_minutes=60,
        assessment_scoring="percent",
        pass_pct=65,
        penalty_for_wrong_answers=False,
        labs_enabled=True,
        strategy_enabled=False,
    )
    return Attempt(
        id=1,
        topic=topic,
        attempt_type="mock",
        started_at=started_at or datetime.now(UTC),
        finished_at=datetime.now(UTC) if finished else None,
        score_raw=0 if finished else None,
        score_scaled=0 if finished else None,
        passed=False if finished else None,
        questions=[],
        responses=[],
    )


def test_active_local_mock_hides_grading_and_review() -> None:
    attempt = mock_attempt()
    assert attempt_out(attempt).questions == []
    with pytest.raises(AttemptError, match="todavía no terminó"):
        review_out(attempt)
    assert review_out(mock_attempt(finished=True)).finished_at is not None


def test_local_mock_rejects_late_answers_before_grading() -> None:
    attempt = mock_attempt(started_at=datetime(2020, 1, 1, tzinfo=UTC))
    with pytest.raises(AttemptError, match="tiempo del intento terminó"):
        submit_response(None, attempt, User(id=1, display_name="Estudiante"), 1, [1])  # type: ignore[arg-type]


def test_removed_purchase_route_is_unavailable() -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/t/playwright/progress/streak-freeze",
            headers={"X-LearnUp-Token": app.state.api_token},
        )
        assert response.status_code == 404
