from __future__ import annotations

import random
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.constants import (
    DEFAULT_DOMAIN_DRILL_QUESTION_COUNT,
    DEFAULT_PRACTICE_QUESTION_COUNT,
    QUICK_DRILL_QUESTION_COUNT,
)
from app.models import (
    Attempt,
    AttemptQuestion,
    AttemptType,
    Domain,
    MockExam,
    MockExamQuestion,
    Objective,
    Question,
    Response,
    ResponseChoice,
    Topic,
    User,
)
from app.schemas import (
    AttemptFinishOut,
    AttemptOut,
    AttemptReviewOut,
    ChoiceReviewOut,
    QuestionPromptOut,
    QuestionReviewOut,
    ResponseResult,
)
from app.services import gamification
from app.services.grading import (
    grade_question,
    prompt_choices,
    review_choices,
)
from app.services.mastery import apply_mastery


class AttemptError(ValueError):
    pass


def _question_loaders():
    return (
        selectinload(Attempt.questions)
        .selectinload(AttemptQuestion.question)
        .selectinload(Question.choices),
        selectinload(Attempt.questions)
        .selectinload(AttemptQuestion.question)
        .selectinload(Question.objective)
        .selectinload(Objective.domain),
        selectinload(Attempt.responses).selectinload(Response.choices),
        selectinload(Attempt.responses)
        .selectinload(Response.question)
        .selectinload(Question.choices),
        selectinload(Attempt.topic),
    )


def get_attempt(session: Session, attempt_id: int, topic_id: int) -> Attempt:
    attempt = session.execute(
        select(Attempt)
        .where(Attempt.id == attempt_id, Attempt.topic_id == topic_id)
        .options(*_question_loaders())
    ).scalar_one_or_none()
    if attempt is None:
        raise AttemptError("Intento inexistente.")
    return attempt


def _random_questions(questions: list[Question], count: int) -> list[Question]:
    if not questions:
        raise AttemptError("No hay preguntas disponibles para este alcance.")
    return random.SystemRandom().sample(questions, min(count, len(questions)))


def create_attempt(
    session: Session,
    topic: Topic,
    user: User,
    attempt_type: str,
    domain_code: str | None = None,
    objective_code: str | None = None,
    question_count: int | None = None,
) -> Attempt:
    try:
        kind = AttemptType(attempt_type)
    except ValueError as exc:
        raise AttemptError("Tipo de intento desconocido.") from exc
    selected: list[Question]
    mock: MockExam | None = None
    if kind is AttemptType.MOCK:
        if domain_code or objective_code or question_count:
            raise AttemptError("La evaluación fija no admite filtros ni otra cantidad.")
        if not topic.assessment_enabled:
            raise AttemptError("Este tema no tiene evaluación final.")
        mock = session.execute(
            select(MockExam)
            .where(MockExam.topic_id == topic.id)
            .options(
                selectinload(MockExam.questions)
                .selectinload(MockExamQuestion.question)
                .selectinload(Question.choices)
            )
        ).scalar_one()
        selected = [item.question for item in mock.questions]
        random.SystemRandom().shuffle(selected)
    else:
        query = (
            select(Question)
            .join(Objective)
            .join(Domain)
            .where(Domain.topic_id == topic.id, Question.is_mock_eligible.is_(True))
            .options(selectinload(Question.choices), selectinload(Question.objective))
        )
        if kind is AttemptType.DOMAIN_DRILL:
            if not domain_code or objective_code:
                raise AttemptError("La práctica de dominio requiere un único dominio.")
            query = query.where(Domain.code == domain_code)
            count = question_count or DEFAULT_DOMAIN_DRILL_QUESTION_COUNT
        elif kind is AttemptType.PRACTICE:
            if domain_code:
                raise AttemptError("La práctica usa objetivo o alcance general, no dominio.")
            if objective_code:
                query = query.where(Objective.code == objective_code)
            count = question_count or DEFAULT_PRACTICE_QUESTION_COUNT
        else:
            if domain_code or objective_code or question_count:
                raise AttemptError("El repaso rápido no admite filtros.")
            count = QUICK_DRILL_QUESTION_COUNT
        selected = _random_questions(list(session.execute(query).scalars()), count)
    attempt = Attempt(
        user_id=user.id,
        topic_id=topic.id,
        attempt_type=kind.value,
        mock_exam_id=mock.id if mock else None,
        started_at=datetime.now(UTC),
    )
    session.add(attempt)
    session.flush()
    for position, question in enumerate(selected):
        session.add(
            AttemptQuestion(
                attempt_id=attempt.id, question_id=question.id, position=position
            )
        )
    session.commit()
    return get_attempt(session, attempt.id, topic.id)


def attempt_label(attempt: Attempt) -> str:
    if attempt.attempt_type == AttemptType.QUICK_DRILL.value:
        return "Repaso rápido"
    if attempt.attempt_type == AttemptType.MOCK.value:
        return "Evaluación final"
    if not attempt.questions:
        return "Práctica"
    objective = attempt.questions[0].question.objective
    if attempt.attempt_type == AttemptType.DOMAIN_DRILL.value:
        return f"Práctica de módulo: {objective.domain.name}"
    return f"Práctica: {objective.title}"


def attempt_out(attempt: Attempt) -> AttemptOut:
    correctness = {
        response.question_id: response.is_correct for response in attempt.responses
    }
    answered = set(correctness)
    questions = [
        QuestionPromptOut(
            question_id=item.question.id,
            external_id=item.question.external_id,
            position=item.position,
            question_type=item.question.question_type,
            stem_markdown=item.question.stem_markdown,
            choices=prompt_choices(item.question, attempt.id),
            answered=item.question.id in answered,
            is_correct=(
                None
                if attempt.attempt_type == AttemptType.MOCK.value
                and attempt.finished_at is None
                else correctness.get(item.question.id)
            ),
        )
        for item in sorted(attempt.questions, key=lambda value: value.position)
    ]
    return AttemptOut(
        id=attempt.id,
        topic_slug=attempt.topic.slug,
        attempt_type=attempt.attempt_type,
        label=attempt_label(attempt),
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        score_raw=attempt.score_raw,
        score_scaled=attempt.score_scaled,
        passed=attempt.passed,
        minutes_allowed=(
            attempt.topic.assessment_minutes
            if attempt.attempt_type == AttemptType.MOCK.value
            else None
        ),
        questions=questions,
    )


def submit_response(
    session: Session,
    attempt: Attempt,
    user: User,
    question_id: int,
    selected_choice_ids: list[int],
) -> ResponseResult:
    if attempt.finished_at is not None:
        raise AttemptError("El intento ya terminó.")
    if attempt.attempt_type == AttemptType.MOCK.value:
        started_at = attempt.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        deadline = started_at.timestamp() + attempt.topic.assessment_minutes * 60
        if datetime.now(UTC).timestamp() >= deadline:
            raise AttemptError("El tiempo del intento terminó.")
    attempt_question = next(
        (item for item in attempt.questions if item.question_id == question_id), None
    )
    if attempt_question is None:
        raise AttemptError("La pregunta no pertenece al intento.")
    if any(response.question_id == question_id for response in attempt.responses):
        raise AttemptError("La pregunta ya fue respondida.")
    question = attempt_question.question
    try:
        correct = grade_question(question, selected_choice_ids)
    except ValueError as exc:
        raise AttemptError(str(exc)) from exc
    response = Response(
        attempt_id=attempt.id,
        question_id=question.id,
        is_correct=correct,
        responded_at=datetime.now(UTC),
    )
    session.add(response)
    session.flush()
    for choice_id in set(selected_choice_ids):
        session.add(ResponseChoice(response_id=response.id, choice_id=choice_id))
    if attempt.attempt_type == AttemptType.MOCK.value:
        session.commit()
        return ResponseResult(
            question_id=question.id,
            recorded=True,
            is_correct=None,
            explanation_markdown=None,
            choices=[],
            xp_awarded=0,
            badges_earned=[],
        )
    apply_mastery(session, user.id, question.objective_id, correct)
    xp, badges = gamification.on_answer(session, user, correct)
    session.commit()
    return ResponseResult(
        question_id=question.id,
        is_correct=correct,
        explanation_markdown=question.explanation_markdown,
        choices=review_choices(question, attempt.id),
        xp_awarded=xp,
        badges_earned=badges,
    )


def finish_attempt(
    session: Session, attempt: Attempt, user: User
) -> AttemptFinishOut:
    if attempt.finished_at is not None:
        raise AttemptError("El intento ya terminó.")
    total = len(attempt.questions)
    score_raw = sum(1 for response in attempt.responses if response.is_correct)
    attempt.score_raw = score_raw
    attempt.finished_at = datetime.now(UTC)
    if attempt.topic.assessment_scoring == "percent":
        attempt.score_scaled = (
            round(100 * score_raw / total) if attempt.attempt_type == "mock" else None
        )
        attempt.passed = (
            score_raw / total >= (attempt.topic.pass_pct or 0) / 100
            if attempt.attempt_type == "mock" and total
            else None
        )
    elif attempt.topic.assessment_scoring == "scaled":
        maximum = attempt.topic.max_score_scaled or 1000
        attempt.score_scaled = round(maximum * score_raw / total) if total else 0
        attempt.passed = (
            attempt.score_scaled >= (attempt.topic.pass_score_scaled or 0)
            if attempt.attempt_type == "mock"
            else None
        )
    else:
        raise AttemptError("Modo de puntuación desconocido.")
    xp, badges = gamification.on_finish(
        session,
        user,
        attempt.attempt_type,
        score_raw,
        total,
        attempt.passed,
    )
    session.commit()
    return AttemptFinishOut(
        id=attempt.id,
        score_raw=score_raw,
        total_questions=total,
        score_scaled=attempt.score_scaled,
        passed=attempt.passed,
        xp_awarded=xp,
        badges_earned=badges,
    )


def review_out(attempt: Attempt) -> AttemptReviewOut:
    if attempt.finished_at is None:
        raise AttemptError("El intento todavía no terminó.")
    response_by_question = {
        response.question_id: response for response in attempt.responses
    }
    rows: list[QuestionReviewOut] = []
    for item in sorted(attempt.questions, key=lambda value: value.position):
        question = item.question
        response = response_by_question.get(question.id)
        selected = (
            [response_choice.choice_id for response_choice in response.choices]
            if response
            else []
        )
        rows.append(
            QuestionReviewOut(
                question_id=question.id,
                external_id=question.external_id,
                position=item.position,
                question_type=question.question_type,
                stem_markdown=question.stem_markdown,
                explanation_markdown=question.explanation_markdown,
                choices=review_choices(question, attempt.id),
                selected_choice_ids=selected,
                is_correct=bool(response and response.is_correct),
            )
        )
    return AttemptReviewOut(
        attempt_id=attempt.id,
        attempt_type=attempt.attempt_type,
        score_raw=attempt.score_raw,
        total_questions=len(attempt.questions),
        score_scaled=attempt.score_scaled,
        passed=attempt.passed,
        finished_at=attempt.finished_at,
        questions=rows,
    )
