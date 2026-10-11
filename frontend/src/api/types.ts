export type ContentId = number | string;

export interface Topic {
  id: ContentId;
  slug: string;
  name: string;
  description: string;
  syllabus_version: string;
  assessment_enabled: boolean;
  assessment_question_count: number;
  assessment_minutes: number;
  assessment_scoring: string;
  pass_pct: number | null;
  pass_score_scaled: number | null;
  max_score_scaled: number | null;
  penalty_for_wrong_answers: boolean;
  labs_enabled: boolean;
  strategy_enabled: boolean;
}

export interface TopicSummary {
  slug: string;
  name: string;
  description: string;
  syllabus_version: string;
  domain_count: number;
  objective_count: number;
  overall_ready_pct: number;
}

export interface Objective {
  id: ContentId;
  code: string;
  title: string;
  description: string;
}

export interface Domain {
  id: ContentId;
  code: string;
  name: string;
  weight_pct: number;
  objectives: Objective[];
}

export interface ContentInfo {
  syllabus_version: string;
  domain_count: number;
  objective_count: number;
  lesson_count: number;
  question_count: number;
  lab_count: number;
}

export interface About {
  app_version: string;
  app_markdown: string;
  intake_markdown: string;
  sources_markdown: string;
  content_changes_markdown: string;
}

export interface FaqEntry {
  index: number;
  question: string;
  selected_text: string | null;
  answer_markdown: string;
}

export type VideoJobStatus = "idle" | "running" | "done" | "error";
export interface VideoStatus {
  status: VideoJobStatus;
  error: string | null;
}

export interface LessonListItem {
  id: ContentId;
  slug: string;
  title: string;
  objective_code: string;
  objective_title: string;
  domain_code: string;
  domain_name: string;
  body_markdown: string;
  why_it_matters_markdown: string;
  video_status: VideoJobStatus;
}

export interface Lesson {
  id: ContentId;
  slug: string;
  title: string;
  objective_code: string;
  objective_title: string;
  domain_code: string;
  domain_name: string;
  body_markdown: string;
  why_it_matters_markdown: string;
  faq: FaqEntry[];
}

export interface Choice {
  id: ContentId;
  position: number;
  text_markdown: string;
}

export interface GradedChoice extends Choice {
  is_correct: boolean;
  explanation_markdown: string;
}

export interface Badge {
  code: string;
  name: string;
  description: string;
  icon: string;
  earned_at: string | null;
}

export interface AttemptQuestion {
  question_id: ContentId;
  external_id: string;
  position: number;
  question_type: "single" | "multi";
  stem_markdown: string;
  choices: Choice[];
  answered: boolean;
  is_correct: boolean | null;
}

export interface ReviewQuestion {
  question_id: ContentId;
  external_id: string;
  position: number;
  question_type: "single" | "multi";
  stem_markdown: string;
  explanation_markdown: string;
  choices: GradedChoice[];
  selected_choice_ids: ContentId[];
  is_correct: boolean;
}

export interface Attempt {
  id: number;
  topic_slug: string;
  attempt_type: "practice" | "domain_drill" | "quick_drill" | "mock";
  label: string;
  started_at: string;
  finished_at: string | null;
  score_raw: number | null;
  score_scaled: number | null;
  passed: boolean | null;
  content_version?: string;
  release_active?: boolean;
  minutes_allowed: number | null;
  questions: AttemptQuestion[];
}

export interface ResponseResult {
  question_id: ContentId;
  recorded?: boolean;
  is_correct: boolean | null;
  explanation_markdown: string | null;
  choices: GradedChoice[];
  xp_awarded: number;
  badges_earned: Badge[];
}

export interface FinishResult {
  id: number;
  score_raw: number;
  total_questions: number;
  score_scaled: number | null;
  passed: boolean | null;
  xp_awarded: number;
  badges_earned: Badge[];
}

export interface Review {
  attempt_id: number;
  attempt_type: string;
  score_raw: number | null;
  total_questions: number;
  score_scaled: number | null;
  passed: boolean | null;
  finished_at: string | null;
  content_version?: string;
  questions: ReviewQuestion[];
}

export interface LabSelfCheck {
  position: number;
  prompt_markdown: string;
  kind: string;
  hint_available: boolean;
}

export interface Lab {
  id: ContentId;
  slug: string;
  title: string;
  objective_code: string;
  objective_title: string;
  domain_code: string;
  scenario_markdown: string;
  setup_sql: string;
  task_markdown: string;
  expected_result: string;
  faq: FaqEntry[];
  self_check: LabSelfCheck[];
  passed: boolean;
}

export interface LabListItem {
  id: ContentId;
  slug: string;
  title: string;
  objective_code: string;
  objective_title: string;
  domain_code: string;
  scenario_markdown: string;
  task_markdown: string;
  self_check_markdown: string[];
  passed: boolean;
}

export interface LabCheckResultItem {
  position: number;
  prompt_markdown: string;
  passed: boolean;
}

export interface LabCheckResult {
  passed: boolean;
  results: LabCheckResultItem[];
  badges_earned: Badge[];
}

export interface ReviewQueueItem {
  objective_code: string;
  objective_title: string;
  status: "weak" | "due" | "new";
}

export interface DomainReadiness {
  code: string;
  name: string;
  weight_pct: number;
  ready_pct: number;
}

export interface AttemptSummary {
  id: number;
  attempt_type: string;
  started_at: string;
  finished_at: string | null;
  score_raw: number | null;
  score_scaled: number | null;
  passed: boolean | null;
  total_questions: number;
  content_version?: string;
  release_active?: boolean;
}

export interface StudyPlanItem {
  objective_code: string;
  objective_title: string;
  estimated_week: number;
}

export interface Dashboard {
  domain_readiness: DomainReadiness[];
  domain_ready_pct: number;
  labs_pct: number;
  strategy_pct: number;
  overall_ready_pct: number;
  exam_ready: boolean;
  xp: number;
  review_queue: ReviewQueueItem[];
  attempt_history: AttemptSummary[];
  study_plan: StudyPlanItem[];
}

export interface StrategyLessonListItem {
  id: ContentId;
  slug: string;
  title: string;
  topic: string;
  read: boolean;
}

export interface StrategyLesson {
  id: ContentId;
  slug: string;
  title: string;
  topic: string;
  body_markdown: string;
  why_it_matters_markdown: string;
  faq: FaqEntry[];
  read: boolean;
}

export interface StrategyQuestion {
  id: ContentId;
  external_id: string;
  topic: string;
  question_type: string;
  stem_markdown: string;
  choices: Choice[];
}

export interface StrategyCheckResult {
  question_id: ContentId;
  is_correct: boolean;
  explanation_markdown: string;
  choices: GradedChoice[];
}

export type AskOutcome =
  | { type: "answered"; entry: FaqEntry }
  | { type: "insufficient" };

export type QuotaStatus =
  | { enabled: false }
  | {
      enabled: true;
      costs: { current_document: number; full_source: number };
      rate: QuotaWindow;
      daily: QuotaWindow;
      monthly: QuotaWindow;
      global_monthly: QuotaWindow;
      active_requests: number;
      max_concurrency: number;
    };

export interface QuotaWindow {
  used: number;
  limit: number;
  remaining: number;
  resets_at: string;
}

export type StreamEvent =
  | { type: "delta"; delta: string }
  | { type: "insufficient" }
  | ({
      type: "result";
      index: number;
      question: string;
      selected_text: string | null;
      answer_markdown: string;
    });
