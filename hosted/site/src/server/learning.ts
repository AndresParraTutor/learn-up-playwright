import type { AuthorizedUser } from "./auth";
import { requireTopic, type TopicRow } from "./catalog";
import { all, first, requireDatabase } from "./db";
import { ApiError } from "./http";
import type { D1Database, D1PreparedStatement, Env } from "./platform";
import {
  optionalPositiveInteger,
  optionalString,
  readJsonObject,
  requiredString,
  requiredStringArray,
  requireIdempotencyKey,
  requireSameOriginMutation,
} from "./request";

const DEFAULT_QUESTION_COUNT = 10;
const XP_PER_CORRECT_ANSWER = 10;
const XP_MOCK_PASS_BONUS = 200;

type AttemptType = "practice" | "domain_drill" | "quick_drill" | "mock";

interface AttemptRow {
  id: number;
  user_id: number;
  release_id: string;
  topic_slug: string;
  attempt_type: AttemptType;
  label: string;
  minutes_allowed: number | null;
  started_at: string;
  finished_at: string | null;
  score_raw: number | null;
  score_scaled: number | null;
  passed: number | null;
  content_version: string;
}

interface AttemptQuestionRow {
  question_id: string;
  external_id: string;
  position: number;
  question_type: "single" | "multi";
  stem_markdown: string;
  explanation_markdown: string;
  objective_id: string;
  answered: number;
  is_correct: number | null;
}

interface ChoiceRow {
  id: string;
  question_id: string;
  position: number;
  text_markdown: string;
  correct: number;
  explanation_markdown: string;
}

interface BadgeRow {
  code: string;
  name: string;
  description: string;
  icon: string;
  earned_at: string | null;
}

interface LabCheckRow {
  position: number;
  prompt_markdown: string;
  kind: string;
  expected_value: string;
  case_sensitive: number;
}


function randomIntegerId(): number {
  const words = crypto.getRandomValues(new Uint32Array(2));
  const value = (words[0] & 0x1fffff) * 0x1_0000_0000 + words[1];
  return value || 1;
}

function shuffled<T>(values: T[]): T[] {
  const result = [...values];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const sample = crypto.getRandomValues(new Uint32Array(1))[0];
    const target = sample % (index + 1);
    [result[index], result[target]] = [result[target], result[index]];
  }
  return result;
}

function hash32(value: string): number {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

function orderChoices(rows: ChoiceRow[], attemptId: number): ChoiceRow[] {
  return [...rows].sort((left, right) => {
    const difference = hash32(`${attemptId}:${left.id}`) - hash32(`${attemptId}:${right.id}`);
    return difference || left.id.localeCompare(right.id);
  });
}

async function transactionalBatch(
  db: D1Database,
  statements: D1PreparedStatement[],
  conflictMessage = "No se pudo guardar el cambio.",
): Promise<void> {
  try {
    const results = await db.batch(statements);
    if (results.some((result) => !result.success)) throw new Error("D1 batch failed.");
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    if (/constraint|unique|already exists|trigger/i.test(detail)) {
      throw new ApiError(409, "state_conflict", conflictMessage);
    }
    throw new ApiError(503, "database_unavailable", "No se pudo guardar el cambio.");
  }
}

async function loadAttempt(
  env: Env,
  user: AuthorizedUser,
  topic: TopicRow,
  attemptId: number,
): Promise<AttemptRow> {
  const db = requireDatabase(env.DB);
  const row = await first<AttemptRow>(
    db,
    `SELECT a.id, a.user_id, a.release_id, a.topic_slug, a.attempt_type, a.label,
       a.minutes_allowed, a.started_at, a.finished_at, a.score_raw, a.score_scaled,
       a.passed, r.content_version
     FROM attempts a
     JOIN content_releases r ON r.id = a.release_id
     WHERE a.id = ?1 AND a.user_id = ?2 AND a.topic_slug = ?3`,
    attemptId,
    user.id,
    topic.slug,
  );
  if (!row) throw new ApiError(404, "attempt_not_found", "No se encontró el intento.");
  return row;
}

async function attemptQuestions(db: D1Database, attemptId: number): Promise<AttemptQuestionRow[]> {
  return all<AttemptQuestionRow>(
    db,
    `SELECT q.id AS question_id, q.external_id, aq.position, q.question_type,
       q.stem_markdown, q.explanation_markdown, q.objective_id,
       CASE WHEN r.id IS NULL THEN 0 ELSE 1 END AS answered, r.is_correct
     FROM attempt_questions aq
     JOIN questions q ON q.release_id = aq.release_id AND q.id = aq.question_id
     LEFT JOIN responses r ON r.attempt_id = aq.attempt_id AND r.question_id = aq.question_id
     WHERE aq.attempt_id = ?1
     ORDER BY aq.position`,
    attemptId,
  );
}

async function attemptChoices(db: D1Database, attemptId: number): Promise<ChoiceRow[]> {
  return all<ChoiceRow>(
    db,
    `SELECT c.id, c.question_id, c.position, c.text_markdown, c.correct,
       c.explanation_markdown
     FROM attempt_questions aq
     JOIN question_choices c
       ON c.release_id = aq.release_id AND c.question_id = aq.question_id
     WHERE aq.attempt_id = ?1
     ORDER BY c.question_id, c.position`,
    attemptId,
  );
}

function promptChoice(row: ChoiceRow, position: number) {
  return { id: row.id, position, text_markdown: row.text_markdown };
}

function reviewChoice(row: ChoiceRow, position: number) {
  return {
    ...promptChoice(row, position),
    is_correct: Boolean(row.correct),
    explanation_markdown: row.explanation_markdown,
  };
}

async function attemptOut(
  db: D1Database,
  attempt: AttemptRow,
  activeReleaseId: string,
): Promise<unknown> {
  const [questions, choices] = await Promise.all([
    attemptQuestions(db, attempt.id),
    attemptChoices(db, attempt.id),
  ]);
  return {
    id: attempt.id,
    topic_slug: attempt.topic_slug,
    attempt_type: attempt.attempt_type,
    label: attempt.label,
    started_at: attempt.started_at,
    finished_at: attempt.finished_at,
    score_raw: attempt.score_raw,
    score_scaled: attempt.score_scaled,
    passed: attempt.passed === null ? null : Boolean(attempt.passed),
    content_version: attempt.content_version,
    release_active: attempt.release_id === activeReleaseId,
    minutes_allowed: attempt.minutes_allowed,
    questions: questions.map((question) => ({
      question_id: question.question_id,
      external_id: question.external_id,
      position: question.position,
      question_type: question.question_type,
      stem_markdown: question.stem_markdown,
      choices: orderChoices(
        choices.filter((choice) => choice.question_id === question.question_id),
        attempt.id,
      ).map(promptChoice),
      answered: Boolean(question.answered),
      is_correct:
        attempt.attempt_type === "mock" && !attempt.finished_at
          ? null
          : question.is_correct === null ? null : Boolean(question.is_correct),
    })),
  };
}

function attemptLabel(
  attemptType: AttemptType,
  objectiveTitle?: string,
  domainName?: string,
): string {
  if (attemptType === "quick_drill") return "Repaso rápido";
  if (attemptType === "mock") return "Evaluación final";
  if (attemptType === "domain_drill") return `Práctica de módulo: ${domainName ?? "Módulo"}`;
  return objectiveTitle ? `Práctica: ${objectiveTitle}` : "Práctica general";
}

export async function createAttempt(
  request: Request,
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
): Promise<unknown> {
  const body = await readJsonObject(request);
  const rawType = requiredString(body, "attempt_type", 32);
  if (!["practice", "domain_drill", "quick_drill", "mock"].includes(rawType)) {
    throw new ApiError(400, "attempt_type_invalid", "El tipo de intento no es válido.");
  }
  const attemptType = rawType as AttemptType;
  const domainCode = optionalString(body, "domain_code", 32);
  const objectiveCode = optionalString(body, "objective_code", 32);
  const requestedCount = optionalPositiveInteger(body, "question_count", 100);
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  if (attemptType === "mock" && (domainCode || objectiveCode || requestedCount)) {
    throw new ApiError(400, "attempt_scope_invalid", "La evaluación final no admite filtros.");
  }
  if (attemptType === "mock" && !topic.assessment_enabled) {
    throw new ApiError(400, "assessment_disabled", "Este tema no tiene evaluación final.");
  }
  if (attemptType === "domain_drill" && (!domainCode || objectiveCode)) {
    throw new ApiError(400, "attempt_scope_invalid", "La práctica de módulo requiere un único módulo.");
  }
  if (attemptType === "practice" && domainCode) {
    throw new ApiError(400, "attempt_scope_invalid", "La práctica no admite un filtro de módulo.");
  }
  if (attemptType === "quick_drill" && (domainCode || objectiveCode || requestedCount)) {
    throw new ApiError(400, "attempt_scope_invalid", "El repaso rápido no admite filtros.");
  }

  const values: unknown[] = [topic.release_id];
  let selectionSql = `SELECT q.id, q.objective_id, o.title AS objective_title,
    d.name AS domain_name
    FROM questions q
    JOIN objectives o ON o.release_id = q.release_id AND o.id = q.objective_id
    JOIN domains d ON d.release_id = o.release_id AND d.id = o.domain_id
    WHERE q.release_id = ?1 AND q.mock_eligible = 1`;
  if (attemptType === "mock") {
    selectionSql = `SELECT q.id, q.objective_id, o.title AS objective_title,
      d.name AS domain_name
      FROM mock_exams m
      JOIN mock_exam_questions mq ON mq.release_id = m.release_id AND mq.mock_id = m.id
      JOIN questions q ON q.release_id = mq.release_id AND q.id = mq.question_id
      JOIN objectives o ON o.release_id = q.release_id AND o.id = q.objective_id
      JOIN domains d ON d.release_id = o.release_id AND d.id = o.domain_id
      WHERE m.release_id = ?1 ORDER BY mq.position`;
  } else if (attemptType === "domain_drill") {
    values.push(domainCode);
    selectionSql += " AND d.code = ?2";
  } else if (attemptType === "practice" && objectiveCode) {
    values.push(objectiveCode);
    selectionSql += " AND o.code = ?2";
  }
  const candidates = await all<{
    id: string;
    objective_id: string;
    objective_title: string;
    domain_name: string;
  }>(db, selectionSql, ...values);
  if (candidates.length === 0) {
    throw new ApiError(400, "questions_unavailable", "No hay preguntas para este alcance.");
  }
  const count = attemptType === "mock" ? candidates.length : requestedCount ?? DEFAULT_QUESTION_COUNT;
  if (attemptType === "mock" && candidates.length !== topic.assessment_question_count) {
    throw new ApiError(503, "assessment_invalid", "La evaluación final no está configurada correctamente.");
  }
  const selected = shuffled(candidates).slice(0, Math.min(count, candidates.length));
  const id = randomIntegerId();
  const startedAt = new Date().toISOString();
  const label = attemptLabel(attemptType, selected[0]?.objective_title, selected[0]?.domain_name);
  const minutesAllowed = attemptType === "mock" ? topic.assessment_minutes : null;
  const statements = [
    db.prepare(
      `INSERT INTO attempts
       (id, user_id, release_id, topic_slug, attempt_type, label, minutes_allowed, started_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)`,
    ).bind(id, user.id, topic.release_id, topic.slug, attemptType, label, minutesAllowed, startedAt),
    ...selected.map((question, position) =>
      db.prepare(
        `INSERT INTO attempt_questions (attempt_id, release_id, question_id, position)
         VALUES (?1, ?2, ?3, ?4)`,
      ).bind(id, topic.release_id, question.id, position),
    ),
  ];
  await transactionalBatch(db, statements, "No se pudo crear el intento.");
  return attemptOut(db, await loadAttempt(env, user, topic, id), topic.release_id);
}

function validAttemptId(value: string): number {
  const id = Number(value);
  if (!Number.isSafeInteger(id) || id <= 0) {
    throw new ApiError(404, "attempt_not_found", "No se encontró el intento.");
  }
  return id;
}

export async function getAttempt(
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
  rawAttemptId: string,
): Promise<unknown> {
  const topic = await requireTopic(env, topicSlug);
  const attempt = await loadAttempt(env, user, topic, validAttemptId(rawAttemptId));
  if (attempt.release_id !== topic.release_id && !attempt.finished_at) {
    throw new ApiError(409, "attempt_release_retired", "Este intento pertenece a una versiÃ³n retirada.");
  }
  return attemptOut(requireDatabase(env.DB), attempt, topic.release_id);
}

async function earnedBadges(
  db: D1Database,
  user: AuthorizedUser,
  topicSlug: string,
  candidates: string[],
): Promise<unknown[]> {
  if (candidates.length === 0) return [];
  const unique = [...new Set(candidates)];
  const existing = await all<{ code: string }>(
    db,
    `SELECT badge_code AS code FROM user_badges
     WHERE user_id = ?1 AND badge_code IN (${unique.map((_, index) => `?${index + 2}`).join(", ")})`,
    user.id,
    ...unique,
  );
  const existingCodes = new Set(existing.map((row) => row.code));
  const newCodes = unique.filter((code) => !existingCodes.has(code));
  if (newCodes.length === 0) return [];
  await transactionalBatch(
    db,
    newCodes.map((code) =>
      db.prepare(
        `INSERT OR IGNORE INTO user_badges (user_id, badge_code)
         SELECT ?1, code FROM badges WHERE code = ?2`,
      ).bind(user.id, code),
    ),
  );
  return all<BadgeRow>(
    db,
    `SELECT b.code, b.name, b.description, b.icon, ub.earned_at
     FROM badges b
     JOIN user_badges ub ON ub.badge_code = b.code AND ub.user_id = ?1
     WHERE b.code IN (${newCodes.map((_, index) => `?${index + 2}`).join(", ")})
     ORDER BY b.code`,
    user.id,
    ...newCodes,
  );
}

export async function submitAttemptResponse(
  request: Request,
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
  rawAttemptId: string,
): Promise<unknown> {
  const body = await readJsonObject(request);
  const questionId = requiredString(body, "question_id", 512);
  const selectedChoiceIds = [...new Set(requiredStringArray(body, "selected_choice_ids", 20))];
  if (selectedChoiceIds.length === 0) {
    throw new ApiError(400, "choice_required", "Seleccioná al menos una opción.");
  }
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  const attempt = await loadAttempt(env, user, topic, validAttemptId(rawAttemptId));
  if (attempt.release_id !== topic.release_id) {
    throw new ApiError(409, "attempt_release_retired", "Este intento pertenece a una versiÃ³n retirada.");
  }
  if (attempt.finished_at) throw new ApiError(409, "attempt_finished", "El intento ya terminó.");
  if (
    attempt.minutes_allowed !== null &&
    Date.now() >= new Date(attempt.started_at).getTime() + attempt.minutes_allowed * 60_000
  ) {
    throw new ApiError(409, "attempt_time_expired", "El tiempo del intento terminó.");
  }
  const question = await first<AttemptQuestionRow>(
    db,
    `SELECT q.id AS question_id, q.external_id, aq.position, q.question_type,
       q.stem_markdown, q.explanation_markdown, q.objective_id, 0 AS answered,
       NULL AS is_correct
     FROM attempt_questions aq
     JOIN questions q ON q.release_id = aq.release_id AND q.id = aq.question_id
     WHERE aq.attempt_id = ?1 AND aq.question_id = ?2`,
    attempt.id,
    questionId,
  );
  if (!question) {
    throw new ApiError(400, "question_out_of_scope", "La pregunta no pertenece al intento.");
  }
  const previous = await first<{ id: number }>(
    db,
    "SELECT id FROM responses WHERE attempt_id = ?1 AND question_id = ?2",
    attempt.id,
    questionId,
  );
  if (previous) throw new ApiError(409, "question_answered", "La pregunta ya fue respondida.");
  const choices = await all<ChoiceRow>(
    db,
    `SELECT id, question_id, position, text_markdown, correct, explanation_markdown
     FROM question_choices WHERE release_id = ?1 AND question_id = ?2 ORDER BY position`,
    attempt.release_id,
    questionId,
  );
  const validIds = new Set(choices.map((choice) => choice.id));
  if (selectedChoiceIds.some((id) => !validIds.has(id))) {
    throw new ApiError(400, "choice_out_of_scope", "Una opción no pertenece a la pregunta.");
  }
  if (question.question_type === "single" && selectedChoiceIds.length !== 1) {
    throw new ApiError(400, "choice_count_invalid", "Seleccioná una sola opción.");
  }
  const correctIds = new Set(choices.filter((choice) => choice.correct).map((choice) => choice.id));
  const correct =
    selectedChoiceIds.length === correctIds.size &&
    selectedChoiceIds.every((id) => correctIds.has(id));
  const responseId = randomIntegerId();
  const masteryValue = correct ? 50 : 0;
  const masteryUpdate = correct
    ? "MIN(100, mastery.mastery_pct + 50)"
    : "MAX(0, mastery.mastery_pct - 25)";
  const statements = [
    db.prepare(
      `INSERT INTO responses (id, attempt_id, release_id, question_id, is_correct)
       VALUES (?1, ?2, ?3, ?4, ?5)`,
    ).bind(responseId, attempt.id, topic.release_id, questionId, correct ? 1 : 0),
    ...selectedChoiceIds.map((choiceId) =>
      db.prepare(
        `INSERT INTO response_choices (response_id, release_id, choice_id)
         VALUES (?1, ?2, ?3)`,
      ).bind(responseId, topic.release_id, choiceId),
    ),
    ...(attempt.attempt_type === "mock" ? [] : [
      db.prepare(
        `INSERT INTO mastery (user_id, release_id, objective_id, mastery_pct, due_on)
         VALUES (?1, ?2, ?3, ?4, date('now', ?5))
         ON CONFLICT(user_id, release_id, objective_id) DO UPDATE SET
           mastery_pct = ${masteryUpdate},
           due_on = date('now', CASE WHEN ${masteryUpdate} >= 100 THEN '+7 day' ELSE '+1 day' END),
           updated_at = CURRENT_TIMESTAMP`,
      ).bind(user.id, topic.release_id, question.objective_id, masteryValue, correct ? "+1 day" : "+0 day"),
      db.prepare(
        `INSERT OR IGNORE INTO user_stats (user_id, topic_slug)
         VALUES (?1, ?2)`,
      ).bind(user.id, topic.slug),
      db.prepare(
        `UPDATE user_stats SET
           xp = xp + ?3
         WHERE user_id = ?1 AND topic_slug = ?2`,
      ).bind(user.id, topic.slug, correct ? XP_PER_CORRECT_ANSWER : 0),
    ]),
  ];
  await transactionalBatch(db, statements, "La respuesta ya fue procesada o el intento cambió.");
  const responseCount = await first<{ count: number }>(
    db, "SELECT COUNT(*) AS count FROM responses r JOIN attempts a ON a.id = r.attempt_id WHERE a.user_id = ?1", user.id,
  );
  if (attempt.attempt_type === "mock") {
    return {
      question_id: questionId,
      recorded: true,
      is_correct: null,
      explanation_markdown: null,
      choices: [],
      xp_awarded: 0,
      badges_earned: [],
    };
  }
  const badgeCandidates = [
    ...(responseCount?.count === 1 ? ["first-attempt"] : []),
  ];
  return {
    question_id: questionId,
    is_correct: correct,
    explanation_markdown: question.explanation_markdown,
    choices: orderChoices(choices, attempt.id).map(reviewChoice),
    xp_awarded: correct ? XP_PER_CORRECT_ANSWER : 0,
    badges_earned: await earnedBadges(db, user, topic.slug, badgeCandidates),
  };
}

export async function finishAttempt(
  request: Request,
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
  rawAttemptId: string,
): Promise<unknown> {
  requireSameOriginMutation(request);
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  const attempt = await loadAttempt(env, user, topic, validAttemptId(rawAttemptId));
  if (attempt.release_id !== topic.release_id && !attempt.finished_at) {
    throw new ApiError(409, "attempt_release_retired", "Este intento pertenece a una versiÃ³n retirada.");
  }
  const counts = await first<{ total: number; correct: number }>(
    db,
    `SELECT COUNT(aq.question_id) AS total,
       COALESCE(SUM(CASE WHEN r.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct
     FROM attempt_questions aq
     LEFT JOIN responses r ON r.attempt_id = aq.attempt_id AND r.question_id = aq.question_id
     WHERE aq.attempt_id = ?1`,
    attempt.id,
  );
  const total = counts?.total ?? 0;
  const scoreRaw = attempt.finished_at ? attempt.score_raw ?? 0 : counts?.correct ?? 0;
  let scoreScaled: number | null = attempt.finished_at ? attempt.score_scaled : null;
  let passed: boolean | null = attempt.finished_at
    ? attempt.passed === null ? null : Boolean(attempt.passed)
    : null;
  const existingFinalization = attempt.finished_at
    ? await first<{ xp_awarded: number }>(
        db,
        `SELECT xp_awarded FROM attempt_finalizations
         WHERE attempt_id = ?1 AND user_id = ?2`,
        attempt.id,
        user.id,
      )
    : null;
  let xpAwarded = existingFinalization?.xp_awarded ?? 0;
  let badges: unknown[] = [];
  if (!attempt.finished_at) {
    if (attempt.attempt_type === "mock") {
      if (topic.assessment_scoring === "percent") {
        scoreScaled = total ? Math.round((100 * scoreRaw) / total) : 0;
        passed = total > 0 && scoreScaled >= (topic.pass_pct ?? 0);
      } else if (topic.assessment_scoring === "scaled") {
        scoreScaled = total
          ? Math.round(((topic.max_score_scaled ?? 1000) * scoreRaw) / total)
          : 0;
        passed = scoreScaled >= (topic.pass_score_scaled ?? 0);
      } else {
        throw new ApiError(503, "scoring_invalid", "La puntuación del curso no es válida.");
      }
    }
    xpAwarded = attempt.attempt_type === "mock" && passed ? XP_MOCK_PASS_BONUS : 0;
    const statements = [
      db.prepare(
        `INSERT INTO attempt_finalizations (attempt_id, user_id, xp_awarded)
         VALUES (?1, ?2, ?3)`,
      ).bind(attempt.id, user.id, xpAwarded),
      db.prepare(
        `UPDATE attempts SET finished_at = ?3, score_raw = ?4, score_scaled = ?5, passed = ?6
         WHERE id = ?1 AND user_id = ?2 AND finished_at IS NULL`,
      ).bind(attempt.id, user.id, new Date().toISOString(), scoreRaw, scoreScaled, passed === null ? null : passed ? 1 : 0),
    ];
    if (xpAwarded) {
      statements.push(
        db.prepare("INSERT OR IGNORE INTO user_stats (user_id, topic_slug) VALUES (?1, ?2)").bind(user.id, topic.slug),
        db.prepare("UPDATE user_stats SET xp = xp + ?3 WHERE user_id = ?1 AND topic_slug = ?2").bind(user.id, topic.slug, xpAwarded),
      );
    }
    try {
      const results = await db.batch(statements);
      if (results.some((result) => !result.success)) throw new Error("D1 finish failed.");
    } catch {
      const current = await loadAttempt(env, user, topic, attempt.id);
      if (!current.finished_at) {
        throw new ApiError(503, "database_unavailable", "No se pudo finalizar el intento.");
      }
      const finalization = await first<{ xp_awarded: number }>(
        db,
        `SELECT xp_awarded FROM attempt_finalizations
         WHERE attempt_id = ?1 AND user_id = ?2`,
        attempt.id,
        user.id,
      );
      return {
        id: current.id,
        score_raw: current.score_raw ?? 0,
        total_questions: total,
        score_scaled: current.score_scaled,
        passed: current.passed === null ? null : Boolean(current.passed),
        xp_awarded: finalization?.xp_awarded ?? 0,
        badges_earned: [],
      };
    }
    const badgeCandidates = [
      ...(attempt.attempt_type !== "mock" && total > 0 && scoreRaw === total ? ["clean-sweep"] : []),
    ];
    badges = await earnedBadges(db, user, topic.slug, badgeCandidates);
  }
  return {
    id: attempt.id,
    score_raw: scoreRaw,
    total_questions: total,
    score_scaled: scoreScaled,
    passed,
    xp_awarded: xpAwarded,
    badges_earned: badges,
  };
}

export async function reviewAttempt(
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
  rawAttemptId: string,
): Promise<unknown> {
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  const attempt = await loadAttempt(env, user, topic, validAttemptId(rawAttemptId));
  if (!attempt.finished_at) {
    throw new ApiError(409, "attempt_not_finished", "El intento todavÃ­a no terminÃ³.");
  }
  const [questions, choices, selections] = await Promise.all([
    attemptQuestions(db, attempt.id),
    attemptChoices(db, attempt.id),
    all<{ question_id: string; choice_id: string }>(
      db,
      `SELECT r.question_id, rc.choice_id
       FROM responses r JOIN response_choices rc ON rc.response_id = r.id
       WHERE r.attempt_id = ?1`,
      attempt.id,
    ),
  ]);
  return {
    attempt_id: attempt.id,
    attempt_type: attempt.attempt_type,
    score_raw: attempt.score_raw,
    total_questions: questions.length,
    score_scaled: attempt.score_scaled,
    passed: attempt.passed === null ? null : Boolean(attempt.passed),
    finished_at: attempt.finished_at,
    content_version: attempt.content_version,
    questions: questions.map((question) => ({
      question_id: question.question_id,
      external_id: question.external_id,
      position: question.position,
      question_type: question.question_type,
      stem_markdown: question.stem_markdown,
      explanation_markdown: question.explanation_markdown,
      choices: orderChoices(
        choices.filter((choice) => choice.question_id === question.question_id),
        attempt.id,
      ).map(reviewChoice),
      selected_choice_ids: selections
        .filter((selection) => selection.question_id === question.question_id)
        .map((selection) => selection.choice_id),
      is_correct: Boolean(question.is_correct),
    })),
  };
}

function checkLabAnswer(check: LabCheckRow, answer: string, previous?: string): boolean {
  let actual = answer.trim();
  let expected = check.expected_value.trim();
  if (check.kind === "contains" || check.kind === "exact") {
    if (!check.case_sensitive) {
      actual = actual.toLocaleLowerCase("es-419");
      expected = expected.toLocaleLowerCase("es-419");
    }
    return check.kind === "contains" ? actual.includes(expected) : actual === expected;
  }
  const value = Number(actual);
  if (!Number.isFinite(value)) return false;
  if (check.kind === "number_positive") return value > 0;
  const prior = previous === undefined ? Number.NaN : Number(previous.trim());
  if (!Number.isFinite(prior)) return false;
  if (check.kind === "number_less_than_previous") return value < prior;
  if (check.kind === "number_greater_than_previous") return value > prior;
  throw new ApiError(503, "lab_check_invalid", "El autocontrol no está configurado correctamente.");
}

async function requireLabChecks(
  env: Env,
  topicSlug: string,
  labSlug: string,
): Promise<{ topic: TopicRow; labId: string; checks: LabCheckRow[] }> {
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  const lab = await first<{ id: string }>(
    db,
    "SELECT id FROM labs WHERE release_id = ?1 AND slug = ?2",
    topic.release_id,
    labSlug,
  );
  if (!lab) throw new ApiError(404, "lab_not_found", "No se encontró la práctica.");
  const checks = await all<LabCheckRow>(
    db,
    `SELECT position, prompt_markdown, kind, expected_value, case_sensitive
     FROM lab_checks WHERE release_id = ?1 AND lab_id = ?2 ORDER BY position`,
    topic.release_id,
    lab.id,
  );
  return { topic, labId: lab.id, checks };
}

export async function checkLab(
  request: Request,
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
  labSlug: string,
): Promise<unknown> {
  const body = await readJsonObject(request);
  const answers = requiredStringArray(body, "answers", 50);
  const { topic, labId, checks } = await requireLabChecks(env, topicSlug, labSlug);
  if (answers.length !== checks.length) {
    throw new ApiError(400, "lab_answers_invalid", "La cantidad de respuestas no coincide.");
  }
  const results = checks.map((check, index) => ({
    position: check.position,
    prompt_markdown: check.prompt_markdown,
    passed: checkLabAnswer(check, answers[index], index > 0 ? answers[index - 1] : undefined),
  }));
  const passed = results.every((result) => result.passed);
  const db = requireDatabase(env.DB);
  await transactionalBatch(
    db,
    [
      db.prepare(
        `INSERT INTO lab_progress
         (user_id, release_id, lab_id, attempt_count, last_checked_at, passed_at)
         VALUES (?1, ?2, ?3, 1, CURRENT_TIMESTAMP, CASE WHEN ?4 = 1 THEN CURRENT_TIMESTAMP ELSE NULL END)
         ON CONFLICT(user_id, release_id, lab_id) DO UPDATE SET
           attempt_count = lab_progress.attempt_count + 1,
           last_checked_at = CURRENT_TIMESTAMP,
           passed_at = CASE
             WHEN lab_progress.passed_at IS NOT NULL THEN lab_progress.passed_at
             WHEN excluded.passed_at IS NOT NULL THEN excluded.passed_at
             ELSE NULL END`,
      ).bind(user.id, topic.release_id, labId, passed ? 1 : 0),
    ],
  );
  return { passed, results, badges_earned: [] };
}

function checkAt(checks: LabCheckRow[], position: number): LabCheckRow {
  const check = checks.find((item) => item.position === position);
  if (!check) throw new ApiError(404, "lab_check_not_found", "No se encontró el autocontrol.");
  return check;
}

function relativeDescription(kind: string): string | null {
  if (kind === "number_positive") return "Debe ser un número positivo.";
  if (kind === "number_less_than_previous") return "Debe ser menor que tu respuesta anterior.";
  if (kind === "number_greater_than_previous") return "Debe ser mayor que tu respuesta anterior.";
  return null;
}

export async function getLabHint(
  env: Env,
  topicSlug: string,
  labSlug: string,
  rawPosition: string,
): Promise<unknown> {
  const position = Number(rawPosition);
  if (!Number.isInteger(position) || position < 0) {
    throw new ApiError(404, "lab_check_not_found", "No se encontró el autocontrol.");
  }
  const check = checkAt((await requireLabChecks(env, topicSlug, labSlug)).checks, position);
  const expected = check.expected_value.trim();
  if (["yes", "no", "sí", "si"].includes(expected.toLocaleLowerCase("es-419"))) {
    throw new ApiError(400, "lab_hint_unavailable", "Este autocontrol de sí/no no ofrece pista.");
  }
  const relative = relativeDescription(check.kind);
  const hint = relative ?? expected.split(/\s+/).map((word) => `${word.slice(0, 1).toLocaleLowerCase("es-419")}…`).join(" ");
  return { position, hint };
}

export async function getLabAnswer(
  env: Env,
  topicSlug: string,
  labSlug: string,
  rawPosition: string,
): Promise<unknown> {
  const position = Number(rawPosition);
  if (!Number.isInteger(position) || position < 0) {
    throw new ApiError(404, "lab_check_not_found", "No se encontró el autocontrol.");
  }
  const check = checkAt((await requireLabChecks(env, topicSlug, labSlug)).checks, position);
  const answer = relativeDescription(check.kind) ?? check.expected_value.trim();
  if (!answer) throw new ApiError(503, "lab_check_invalid", "El autocontrol no tiene respuesta.");
  return { position, answer };
}

export async function deleteFaq(
  request: Request,
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
  kind: "lesson" | "lab",
  slug: string,
  rawIndex: string,
): Promise<void> {
  requireSameOriginMutation(request);
  const index = Number(rawIndex);
  if (!Number.isInteger(index) || index < 0) {
    throw new ApiError(404, "faq_not_found", "No se encontró la pregunta guardada.");
  }
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  const table = kind === "lesson" ? "lessons" : "labs";
  const content = await first<{ id: string }>(
    db,
    `SELECT id FROM ${table} WHERE release_id = ?1 AND slug = ?2`,
    topic.release_id,
    slug,
  );
  if (!content) throw new ApiError(404, `${kind}_not_found`, "No se encontró el material.");
  const row = await first<{ id: number }>(
    db,
    `DELETE FROM faq_entries
     WHERE user_id = ?1 AND release_id = ?2 AND content_id = ?3 AND display_index = ?4
     RETURNING id`,
    user.id,
    topic.release_id,
    content.id,
    index,
  );
  if (!row) throw new ApiError(404, "faq_not_found", "No se encontró la pregunta guardada.");
}

export async function listBadges(env: Env, user: AuthorizedUser): Promise<unknown[]> {
  return all<BadgeRow>(
    requireDatabase(env.DB),
    `SELECT b.code, b.name, b.description, b.icon, ub.earned_at
     FROM badges b
     LEFT JOIN user_badges ub ON ub.badge_code = b.code AND ub.user_id = ?1
     WHERE b.code IN ('first-attempt', 'clean-sweep')
        OR b.code LIKE 'domain-%'
     ORDER BY b.code`,
    user.id,
  );
}

export async function recordLessonOpened(
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
  lessonSlug: string,
): Promise<void> {
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  const lesson = await first<{ id: string }>(
    db,
    "SELECT id FROM lessons WHERE release_id = ?1 AND slug = ?2",
    topic.release_id,
    lessonSlug,
  );
  if (!lesson) return;
  try {
    await db.prepare(
      `INSERT INTO lesson_progress (user_id, release_id, lesson_id, last_opened_at)
       VALUES (?1, ?2, ?3, CURRENT_TIMESTAMP)
       ON CONFLICT(user_id, release_id, lesson_id) DO UPDATE SET
         last_opened_at = CURRENT_TIMESTAMP`,
    ).bind(user.id, topic.release_id, lesson.id).run();
  } catch {
    throw new ApiError(503, "database_unavailable", "No se pudo registrar el progreso.");
  }
}
