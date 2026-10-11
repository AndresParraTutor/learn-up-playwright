from datetime import datetime

from pydantic import BaseModel, Field


class TopicOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    syllabus_version: str
    assessment_enabled: bool
    assessment_question_count: int
    assessment_minutes: int
    assessment_scoring: str
    pass_pct: int | None
    pass_score_scaled: int | None
    max_score_scaled: int | None
    penalty_for_wrong_answers: bool
    labs_enabled: bool
    strategy_enabled: bool


class TopicSummaryOut(BaseModel):
    slug: str
    name: str
    description: str
    syllabus_version: str
    domain_count: int
    objective_count: int
    overall_ready_pct: int


class ObjectiveOut(BaseModel):
    id: int
    code: str
    title: str
    description: str


class DomainOut(BaseModel):
    id: int
    code: str
    name: str
    weight_pct: int
    objectives: list[ObjectiveOut] = []


class ContentInfoOut(BaseModel):
    syllabus_version: str
    domain_count: int
    objective_count: int
    lesson_count: int
    question_count: int
    lab_count: int


class AboutOut(BaseModel):
    app_version: str
    app_markdown: str
    intake_markdown: str
    sources_markdown: str
    content_changes_markdown: str


class FaqEntryOut(BaseModel):
    index: int
    question: str
    selected_text: str | None = None
    answer_markdown: str


class LessonListItem(BaseModel):
    id: int
    slug: str
    title: str
    objective_code: str
    objective_title: str
    domain_code: str
    domain_name: str
    body_markdown: str
    why_it_matters_markdown: str
    video_status: str


class LessonOut(BaseModel):
    id: int
    slug: str
    title: str
    objective_code: str
    objective_title: str
    domain_code: str
    domain_name: str
    body_markdown: str
    why_it_matters_markdown: str
    faq: list[FaqEntryOut]


class VideoStatusOut(BaseModel):
    status: str
    error: str | None = None


class ChoiceOut(BaseModel):
    id: int
    position: int
    text_markdown: str


class ChoiceReviewOut(ChoiceOut):
    is_correct: bool
    explanation_markdown: str


class BadgeOut(BaseModel):
    code: str
    name: str
    description: str
    icon: str
    earned_at: datetime | None = None


class QuestionPromptOut(BaseModel):
    question_id: int
    external_id: str
    position: int
    question_type: str
    stem_markdown: str
    choices: list[ChoiceOut]
    answered: bool
    is_correct: bool | None = None


class QuestionReviewOut(BaseModel):
    question_id: int
    external_id: str
    position: int
    question_type: str
    stem_markdown: str
    explanation_markdown: str
    choices: list[ChoiceReviewOut]
    selected_choice_ids: list[int]
    is_correct: bool


class AttemptOut(BaseModel):
    id: int
    topic_slug: str
    attempt_type: str
    label: str
    started_at: datetime
    finished_at: datetime | None
    score_raw: int | None
    score_scaled: int | None
    passed: bool | None
    minutes_allowed: int | None
    questions: list[QuestionPromptOut]


class ResponseResult(BaseModel):
    question_id: int
    recorded: bool = False
    is_correct: bool | None
    explanation_markdown: str | None
    choices: list[ChoiceReviewOut]
    xp_awarded: int
    badges_earned: list[BadgeOut]


class AttemptFinishOut(BaseModel):
    id: int
    score_raw: int
    total_questions: int
    score_scaled: int | None
    passed: bool | None
    xp_awarded: int
    badges_earned: list[BadgeOut]


class AttemptReviewOut(BaseModel):
    attempt_id: int
    attempt_type: str
    score_raw: int | None
    total_questions: int
    score_scaled: int | None
    passed: bool | None
    finished_at: datetime | None
    questions: list[QuestionReviewOut]


class LabSelfCheckOut(BaseModel):
    position: int
    prompt_markdown: str
    kind: str
    hint_available: bool


class LabOut(BaseModel):
    id: int
    slug: str
    title: str
    objective_code: str
    objective_title: str
    domain_code: str
    scenario_markdown: str
    setup_sql: str
    task_markdown: str
    expected_result: str
    faq: list[FaqEntryOut]
    self_check: list[LabSelfCheckOut]
    passed: bool


class LabListItem(BaseModel):
    id: int
    slug: str
    title: str
    objective_code: str
    objective_title: str
    domain_code: str
    scenario_markdown: str
    task_markdown: str
    self_check_markdown: list[str]
    passed: bool


class LabCheckRequest(BaseModel):
    answers: list[str]


class LabCheckResultItem(BaseModel):
    position: int
    prompt_markdown: str
    passed: bool


class LabCheckResult(BaseModel):
    passed: bool
    results: list[LabCheckResultItem]
    badges_earned: list[BadgeOut]


class LabCheckHintOut(BaseModel):
    position: int
    hint: str


class LabCheckAnswerOut(BaseModel):
    position: int
    answer: str


class ReviewQueueItem(BaseModel):
    objective_code: str
    objective_title: str
    status: str


class DomainReadiness(BaseModel):
    code: str
    name: str
    weight_pct: int
    ready_pct: int


class AttemptSummary(BaseModel):
    id: int
    attempt_type: str
    started_at: datetime
    finished_at: datetime | None
    score_raw: int | None
    score_scaled: int | None
    passed: bool | None
    total_questions: int


class StudyPlanItem(BaseModel):
    objective_code: str
    objective_title: str
    estimated_week: int


class DashboardOut(BaseModel):
    domain_readiness: list[DomainReadiness]
    domain_ready_pct: int
    labs_pct: int
    strategy_pct: int
    overall_ready_pct: int
    exam_ready: bool
    xp: int
    review_queue: list[ReviewQueueItem]
    attempt_history: list[AttemptSummary]
    study_plan: list[StudyPlanItem]


class StrategyLessonListItem(BaseModel):
    id: int
    slug: str
    title: str
    topic: str
    read: bool


class StrategyLessonOut(BaseModel):
    id: int
    slug: str
    title: str
    topic: str
    body_markdown: str
    why_it_matters_markdown: str
    faq: list[FaqEntryOut]
    read: bool


class StrategyQuestionOut(BaseModel):
    id: int
    external_id: str
    topic: str
    question_type: str
    stem_markdown: str
    choices: list[ChoiceOut]


class StrategyCheckResult(BaseModel):
    question_id: int
    is_correct: bool
    explanation_markdown: str
    choices: list[ChoiceReviewOut]


class AttemptCreate(BaseModel):
    attempt_type: str
    domain_code: str | None = None
    objective_code: str | None = None
    question_count: int | None = Field(default=None, ge=1, le=100)


class ResponseCreate(BaseModel):
    question_id: int
    selected_choice_ids: list[int]


class QuestionAskRequest(BaseModel):
    selected_text: str = Field(min_length=1, max_length=6000)
    question: str = Field(min_length=1, max_length=2000)
    use_full_sources: bool = False
