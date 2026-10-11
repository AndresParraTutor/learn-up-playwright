from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    Sequence,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(schema="learn")


def utc_now() -> datetime:
    return datetime.now(UTC)


class QuestionType(StrEnum):
    SINGLE = "single"
    MULTI = "multi"


class AttemptType(StrEnum):
    PRACTICE = "practice"
    DOMAIN_DRILL = "domain_drill"
    QUICK_DRILL = "quick_drill"
    MOCK = "mock"


class LabCheckKind(StrEnum):
    CONTAINS = "contains"
    EXACT = "exact"
    NUMBER_POSITIVE = "number_positive"
    NUMBER_LESS_THAN_PREVIOUS = "number_less_than_previous"
    NUMBER_GREATER_THAN_PREVIOUS = "number_greater_than_previous"


class Topic(Base):
    __tablename__ = "topic"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_topic", schema="learn"), primary_key=True
    )
    slug: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    syllabus_version: Mapped[str] = mapped_column(String)
    assessment_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    assessment_question_count: Mapped[int] = mapped_column(Integer, default=0)
    assessment_minutes: Mapped[int] = mapped_column(Integer, default=0)
    assessment_scoring: Mapped[str] = mapped_column(String, default="percent")
    pass_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pass_score_scaled: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_score_scaled: Mapped[int | None] = mapped_column(Integer, nullable=True)
    penalty_for_wrong_answers: Mapped[bool] = mapped_column(Boolean, default=False)
    labs_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    strategy_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    domains: Mapped[list[Domain]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    mock_exams: Mapped[list[MockExam]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class Domain(Base):
    __tablename__ = "domain"
    __table_args__ = (UniqueConstraint("topic_id", "code"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_domain", schema="learn"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("learn.topic.id"))
    code: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    weight_pct: Mapped[int] = mapped_column(Integer)
    syllabus_version: Mapped[str] = mapped_column(String)

    topic: Mapped[Topic] = relationship(back_populates="domains")
    objectives: Mapped[list[Objective]] = relationship(
        back_populates="domain", cascade="all, delete-orphan"
    )


class Objective(Base):
    __tablename__ = "objective"
    __table_args__ = (UniqueConstraint("domain_id", "code"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_objective", schema="learn"), primary_key=True
    )
    domain_id: Mapped[int] = mapped_column(ForeignKey("learn.domain.id"))
    code: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    syllabus_version: Mapped[str] = mapped_column(String)

    domain: Mapped[Domain] = relationship(back_populates="objectives")
    lessons: Mapped[list[Lesson]] = relationship(
        back_populates="objective", cascade="all, delete-orphan"
    )
    questions: Mapped[list[Question]] = relationship(
        back_populates="objective", cascade="all, delete-orphan"
    )
    labs: Mapped[list[Lab]] = relationship(
        back_populates="objective", cascade="all, delete-orphan"
    )


class Lesson(Base):
    __tablename__ = "lesson"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_lesson", schema="learn"), primary_key=True
    )
    objective_id: Mapped[int] = mapped_column(ForeignKey("learn.objective.id"))
    slug: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String)
    body_markdown: Mapped[str] = mapped_column(Text)
    why_it_matters_markdown: Mapped[str] = mapped_column(Text)
    faq_markdown: Mapped[str] = mapped_column(Text, default="")

    objective: Mapped[Objective] = relationship(back_populates="lessons")


class Question(Base):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_question", schema="learn"), primary_key=True
    )
    objective_id: Mapped[int] = mapped_column(ForeignKey("learn.objective.id"))
    external_id: Mapped[str] = mapped_column(String, unique=True)
    question_type: Mapped[str] = mapped_column(String)
    stem_markdown: Mapped[str] = mapped_column(Text)
    explanation_markdown: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(Integer)
    is_mock_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    syllabus_version: Mapped[str] = mapped_column(String)

    objective: Mapped[Objective] = relationship(back_populates="questions")
    choices: Mapped[list[Choice]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="Choice.position"
    )


class Choice(Base):
    __tablename__ = "choice"
    __table_args__ = (UniqueConstraint("question_id", "position"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_choice", schema="learn"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("learn.question.id"))
    position: Mapped[int] = mapped_column(Integer)
    text_markdown: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    distractor_explanation_markdown: Mapped[str] = mapped_column(Text)

    question: Mapped[Question] = relationship(back_populates="choices")


class Lab(Base):
    __tablename__ = "lab"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_lab", schema="learn"), primary_key=True
    )
    objective_id: Mapped[int] = mapped_column(ForeignKey("learn.objective.id"))
    slug: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String)
    scenario_markdown: Mapped[str] = mapped_column(Text)
    setup_sql: Mapped[str] = mapped_column(Text)
    task_markdown: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str] = mapped_column(Text)
    faq_markdown: Mapped[str] = mapped_column(Text, default="")

    objective: Mapped[Objective] = relationship(back_populates="labs")
    checks: Mapped[list[LabCheck]] = relationship(
        back_populates="lab", cascade="all, delete-orphan", order_by="LabCheck.position"
    )


class LabCheck(Base):
    __tablename__ = "lab_check"
    __table_args__ = (UniqueConstraint("lab_id", "position"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_lab_check", schema="learn"), primary_key=True
    )
    lab_id: Mapped[int] = mapped_column(ForeignKey("learn.lab.id"))
    position: Mapped[int] = mapped_column(Integer)
    prompt_markdown: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String)
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)

    lab: Mapped[Lab] = relationship(back_populates="checks")


class MockExam(Base):
    __tablename__ = "mock_exam"
    __table_args__ = (UniqueConstraint("topic_id", "code"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_mock_exam", schema="learn"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("learn.topic.id"))
    code: Mapped[str] = mapped_column(String)
    syllabus_version: Mapped[str] = mapped_column(String)

    topic: Mapped[Topic] = relationship(back_populates="mock_exams")
    questions: Mapped[list[MockExamQuestion]] = relationship(
        back_populates="mock_exam",
        cascade="all, delete-orphan",
        order_by="MockExamQuestion.position",
    )


class MockExamQuestion(Base):
    __tablename__ = "mock_exam_question"
    __table_args__ = (UniqueConstraint("mock_exam_id", "position"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_mock_exam_question", schema="learn"), primary_key=True
    )
    mock_exam_id: Mapped[int] = mapped_column(ForeignKey("learn.mock_exam.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("learn.question.id"))
    position: Mapped[int] = mapped_column(Integer)

    mock_exam: Mapped[MockExam] = relationship(back_populates="questions")
    question: Mapped[Question] = relationship()


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_user", schema="learn"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    streak_freeze_count: Mapped[int] = mapped_column(Integer, default=0)


class StreakFreezePurchase(Base):
    __tablename__ = "streak_freeze_purchase"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_streak_freeze_purchase", schema="learn"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("learn.user.id"))
    topic_slug: Mapped[str] = mapped_column(String)
    idempotency_key: Mapped[str] = mapped_column(String)
    request_fingerprint: Mapped[str] = mapped_column(String)
    xp_after: Mapped[int] = mapped_column(Integer)
    streak_freeze_count_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Attempt(Base):
    __tablename__ = "attempt"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_attempt", schema="learn"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("learn.user.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("learn.topic.id"))
    attempt_type: Mapped[str] = mapped_column(String)
    mock_exam_id: Mapped[int | None] = mapped_column(
        ForeignKey("learn.mock_exam.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    score_raw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_scaled: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    user: Mapped[User] = relationship()
    topic: Mapped[Topic] = relationship()
    mock_exam: Mapped[MockExam | None] = relationship()
    questions: Mapped[list[AttemptQuestion]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="AttemptQuestion.position",
    )
    responses: Mapped[list[Response]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class AttemptQuestion(Base):
    __tablename__ = "attempt_question"
    __table_args__ = (UniqueConstraint("attempt_id", "position"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_attempt_question", schema="learn"), primary_key=True
    )
    attempt_id: Mapped[int] = mapped_column(ForeignKey("learn.attempt.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("learn.question.id"))
    position: Mapped[int] = mapped_column(Integer)

    attempt: Mapped[Attempt] = relationship(back_populates="questions")
    question: Mapped[Question] = relationship()


class Response(Base):
    __tablename__ = "response"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_response", schema="learn"), primary_key=True
    )
    attempt_id: Mapped[int] = mapped_column(ForeignKey("learn.attempt.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("learn.question.id"))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    responded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    attempt: Mapped[Attempt] = relationship(back_populates="responses")
    question: Mapped[Question] = relationship()
    choices: Mapped[list[ResponseChoice]] = relationship(
        back_populates="response", cascade="all, delete-orphan"
    )


class ResponseChoice(Base):
    __tablename__ = "response_choice"
    __table_args__ = (UniqueConstraint("response_id", "choice_id"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_response_choice", schema="learn"), primary_key=True
    )
    response_id: Mapped[int] = mapped_column(ForeignKey("learn.response.id"))
    choice_id: Mapped[int] = mapped_column(ForeignKey("learn.choice.id"))

    response: Mapped[Response] = relationship(back_populates="choices")
    choice: Mapped[Choice] = relationship()


class Mastery(Base):
    __tablename__ = "mastery"
    __table_args__ = (UniqueConstraint("user_id", "objective_id"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_mastery", schema="learn"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("learn.user.id"))
    objective_id: Mapped[int] = mapped_column(ForeignKey("learn.objective.id"))
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    ease_factor: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("2.50"))
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship()
    objective: Mapped[Objective] = relationship()


class LabAttempt(Base):
    __tablename__ = "lab_attempt"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_lab_attempt", schema="learn"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("learn.user.id"))
    lab_id: Mapped[int] = mapped_column(ForeignKey("learn.lab.id"))
    passed: Mapped[bool] = mapped_column(Boolean)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped[User] = relationship()
    lab: Mapped[Lab] = relationship()


class Badge(Base):
    __tablename__ = "badge"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_badge", schema="learn"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String)


class UserBadge(Base):
    __tablename__ = "user_badge"
    __table_args__ = (UniqueConstraint("user_id", "badge_id"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_user_badge", schema="learn"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("learn.user.id"))
    badge_id: Mapped[int] = mapped_column(ForeignKey("learn.badge.id"))
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped[User] = relationship()
    badge: Mapped[Badge] = relationship()


class StrategyLesson(Base):
    __tablename__ = "strategy_lesson"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_strategy_lesson", schema="learn"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("learn.topic.id"))
    topic: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String)
    body_markdown: Mapped[str] = mapped_column(Text)
    why_it_matters_markdown: Mapped[str] = mapped_column(Text)
    faq_markdown: Mapped[str] = mapped_column(Text, default="")


class StrategyQuestion(Base):
    __tablename__ = "strategy_question"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_strategy_question", schema="learn"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("learn.topic.id"))
    topic: Mapped[str] = mapped_column(String)
    external_id: Mapped[str] = mapped_column(String, unique=True)
    question_type: Mapped[str] = mapped_column(String)
    stem_markdown: Mapped[str] = mapped_column(Text)
    explanation_markdown: Mapped[str] = mapped_column(Text)
    choices: Mapped[list[StrategyChoice]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class StrategyChoice(Base):
    __tablename__ = "strategy_choice"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_strategy_choice", schema="learn"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("learn.strategy_question.id"))
    position: Mapped[int] = mapped_column(Integer)
    text_markdown: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    distractor_explanation_markdown: Mapped[str] = mapped_column(Text)

    question: Mapped[StrategyQuestion] = relationship(back_populates="choices")


class StrategyLessonProgress(Base):
    __tablename__ = "strategy_lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "strategy_lesson_id"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_strategy_lesson_progress", schema="learn"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("learn.user.id"))
    strategy_lesson_id: Mapped[int] = mapped_column(
        ForeignKey("learn.strategy_lesson.id")
    )
    read_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class StrategyAttempt(Base):
    __tablename__ = "strategy_attempt"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("seq_strategy_attempt", schema="learn"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("learn.user.id"))
    strategy_question_id: Mapped[int] = mapped_column(
        ForeignKey("learn.strategy_question.id")
    )
    is_correct: Mapped[bool] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
