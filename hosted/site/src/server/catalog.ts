import type { AuthorizedUser } from "./auth";
import { all, first, requireDatabase, requireExpectedContentDigest } from "./db";
import { ApiError } from "./http";
import type { Env } from "./platform";

export interface TopicRow {
  release_id: string;
  id: string;
  slug: string;
  name: string;
  description: string;
  content_version: string;
  assessment_enabled: number;
  assessment_question_count: number;
  assessment_minutes: number;
  assessment_scoring: string;
  pass_pct: number | null;
  pass_score_scaled: number | null;
  max_score_scaled: number | null;
  penalty_for_wrong_answers: number;
  labs_enabled: number;
  strategy_enabled: number;
}

interface TopicSummaryRow extends TopicRow {
  domain_count: number;
  objective_count: number;
}

interface DomainRow {
  id: string;
  code: string;
  name: string;
  weight_pct: number;
}

interface ObjectiveRow {
  id: string;
  domain_id: string;
  code: string;
  title: string;
  description: string;
}

interface LessonRow {
  id: string;
  slug: string;
  title: string;
  objective_code: string;
  objective_title: string;
  domain_code: string;
  domain_name: string;
  body_markdown: string;
  why_it_matters_markdown: string;
  video_available: number;
}

interface LabRow {
  id: string;
  slug: string;
  title: string;
  objective_code: string;
  objective_title: string;
  domain_code: string;
  scenario_markdown: string;
  setup_sql: string;
  task_markdown: string;
  expected_result: string;
  passed: number;
}

interface LabCheckRow {
  position: number;
  prompt_markdown: string;
  kind: string;
  expected_value: string;
}

interface FaqRow {
  display_index: number;
  question: string;
  selected_text: string | null;
  answer_markdown: string;
}

interface AboutRow {
  app_version: string;
  app_markdown: string;
  intake_markdown: string;
  sources_markdown: string;
  content_changes_markdown: string;
}

interface UserStatsRow {
  xp: number;
}

interface MasteryRow {
  objective_id: string;
  mastery_pct: number;
  due_on: string | null;
}

function topicOut(row: TopicRow) {
  return {
    id: row.id,
    slug: row.slug,
    name: row.name,
    description: row.description,
    syllabus_version: row.content_version,
    assessment_enabled: Boolean(row.assessment_enabled),
    assessment_question_count: row.assessment_question_count,
    assessment_minutes: row.assessment_minutes,
    assessment_scoring: row.assessment_scoring,
    pass_pct: row.pass_pct,
    pass_score_scaled: row.pass_score_scaled,
    max_score_scaled: row.max_score_scaled,
    penalty_for_wrong_answers: Boolean(row.penalty_for_wrong_answers),
    labs_enabled: Boolean(row.labs_enabled),
    strategy_enabled: Boolean(row.strategy_enabled),
  };
}

export async function requireTopic(env: Env, slug: string): Promise<TopicRow> {
  const db = requireDatabase(env.DB);
  const expectedDigest = requireExpectedContentDigest(env);
  const topic = await first<TopicRow>(
    db,
    `SELECT r.id AS release_id, t.*
     FROM topics t
     JOIN content_releases r ON r.id = t.release_id
     WHERE r.status = 'active' AND t.slug = ?1 AND r.source_digest = ?2`,
    slug,
    expectedDigest,
  );
  if (!topic) {
    throw new ApiError(503, "content_not_ready", "El contenido alojado todavía no está inicializado.");
  }
  return topic;
}

export async function listTopics(
  env: Env,
  user: AuthorizedUser,
): Promise<unknown[]> {
  const db = requireDatabase(env.DB);
  const expectedDigest = requireExpectedContentDigest(env);
  const rows = await all<TopicSummaryRow>(
    db,
    `SELECT r.id AS release_id, t.*,
       (SELECT COUNT(*) FROM domains d WHERE d.release_id = r.id) AS domain_count,
       (SELECT COUNT(*) FROM objectives o WHERE o.release_id = r.id) AS objective_count
     FROM topics t
     JOIN content_releases r ON r.id = t.release_id
     WHERE r.status = 'active' AND r.source_digest = ?1
     ORDER BY t.name`,
    expectedDigest,
  );
  if (rows.length === 0) {
    throw new ApiError(503, "content_not_ready", "El contenido alojado todavía no está inicializado.");
  }
  return Promise.all(rows.map(async (row) => {
    const dashboard = await getDashboard(env, user, row.slug) as {
      overall_ready_pct: number;
    };
    return {
      slug: row.slug,
      name: row.name,
      description: row.description,
      syllabus_version: row.content_version,
      domain_count: row.domain_count,
      objective_count: row.objective_count,
      overall_ready_pct: dashboard.overall_ready_pct,
    };
  }));
}

export async function getTopic(env: Env, slug: string): Promise<unknown> {
  return topicOut(await requireTopic(env, slug));
}

export async function listDomains(env: Env, slug: string): Promise<unknown[]> {
  const topic = await requireTopic(env, slug);
  const db = requireDatabase(env.DB);
  const [domains, objectives] = await Promise.all([
    all<DomainRow>(
      db,
      "SELECT id, code, name, weight_pct FROM domains WHERE release_id = ?1 ORDER BY sort_order",
      topic.release_id,
    ),
    all<ObjectiveRow>(
      db,
      `SELECT id, domain_id, code, title, description
       FROM objectives WHERE release_id = ?1 ORDER BY sort_order`,
      topic.release_id,
    ),
  ]);
  return domains.map((domain) => ({
    ...domain,
    objectives: objectives
      .filter((objective) => objective.domain_id === domain.id)
      .map(({ domain_id: _domainId, ...objective }) => objective),
  }));
}

const lessonSelect = `SELECT l.id, l.slug, l.title, l.body_markdown,
  l.why_it_matters_markdown, o.code AS objective_code,
  o.title AS objective_title, d.code AS domain_code, d.name AS domain_name,
  CASE WHEN m.available = 1 THEN 1 ELSE 0 END AS video_available
  FROM lessons l
  JOIN objectives o ON o.release_id = l.release_id AND o.id = l.objective_id
  JOIN domains d ON d.release_id = o.release_id AND d.id = o.domain_id
  LEFT JOIN media_objects m ON m.release_id = l.release_id AND m.content_id = l.id`;

function lessonOut(row: LessonRow) {
  return {
    id: row.id,
    slug: row.slug,
    title: row.title,
    objective_code: row.objective_code,
    objective_title: row.objective_title,
    domain_code: row.domain_code,
    domain_name: row.domain_name,
    body_markdown: row.body_markdown,
    why_it_matters_markdown: row.why_it_matters_markdown,
    video_status: row.video_available ? "done" : "idle",
  };
}

export async function listLessons(
  env: Env,
  slug: string,
  objectiveCode?: string,
): Promise<unknown[]> {
  const topic = await requireTopic(env, slug);
  const db = requireDatabase(env.DB);
  const values: unknown[] = [topic.release_id];
  let where = "l.release_id = ?1";
  if (objectiveCode) {
    values.push(objectiveCode);
    where += " AND o.code = ?2";
  }
  const rows = await all<LessonRow>(
    db,
    `${lessonSelect} WHERE ${where} ORDER BY d.sort_order, o.sort_order, l.sort_order`,
    ...values,
  );
  return rows.map(lessonOut);
}

async function faqEntries(
  env: Env,
  user: AuthorizedUser,
  releaseId: string,
  contentId: string,
): Promise<unknown[]> {
  const db = requireDatabase(env.DB);
  const rows = await all<FaqRow>(
    db,
    `SELECT display_index, question, selected_text, answer_markdown
     FROM faq_entries
     WHERE user_id = ?1 AND release_id = ?2 AND content_id = ?3
     ORDER BY display_index`,
    user.id,
    releaseId,
    contentId,
  );
  return rows.map((row) => ({
    index: row.display_index,
    question: row.question,
    selected_text: row.selected_text,
    answer_markdown: row.answer_markdown,
  }));
}

export async function getLesson(
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
  lessonSlug: string,
): Promise<unknown> {
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  const row = await first<LessonRow>(
    db,
    `${lessonSelect} WHERE l.release_id = ?1 AND l.slug = ?2`,
    topic.release_id,
    lessonSlug,
  );
  if (!row) throw new ApiError(404, "lesson_not_found", "No se encontró la lección.");
  return {
    ...lessonOut(row),
    faq: await faqEntries(env, user, topic.release_id, row.id),
  };
}

const labSelect = `SELECT l.id, l.slug, l.title, l.scenario_markdown, l.setup_sql,
  l.task_markdown, l.expected_result, o.code AS objective_code,
  o.title AS objective_title, d.code AS domain_code,
  CASE WHEN la.passed_at IS NULL THEN 0 ELSE 1 END AS passed
  FROM labs l
  JOIN objectives o ON o.release_id = l.release_id AND o.id = l.objective_id
  JOIN domains d ON d.release_id = o.release_id AND d.id = o.domain_id
  LEFT JOIN lab_progress la ON la.user_id = ?1 AND la.release_id = l.release_id AND la.lab_id = l.id`;

export async function listLabs(
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
): Promise<unknown[]> {
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  const rows = await all<LabRow>(
    db,
    `${labSelect} WHERE l.release_id = ?2 ORDER BY d.sort_order, o.sort_order, l.sort_order`,
    user.id,
    topic.release_id,
  );
  return Promise.all(rows.map(async (row) => ({
    id: row.id,
    slug: row.slug,
    title: row.title,
    objective_code: row.objective_code,
    objective_title: row.objective_title,
    domain_code: row.domain_code,
    scenario_markdown: row.scenario_markdown,
    task_markdown: row.task_markdown,
    self_check_markdown: (
      await all<{ prompt_markdown: string }>(
        db,
        "SELECT prompt_markdown FROM lab_checks WHERE release_id = ?1 AND lab_id = ?2 ORDER BY position",
        topic.release_id,
        row.id,
      )
    ).map((item) => item.prompt_markdown),
    passed: Boolean(row.passed),
  })));
}

export async function getLab(
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
  labSlug: string,
): Promise<unknown> {
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  const row = await first<LabRow>(
    db,
    `${labSelect} WHERE l.release_id = ?2 AND l.slug = ?3`,
    user.id,
    topic.release_id,
    labSlug,
  );
  if (!row) throw new ApiError(404, "lab_not_found", "No se encontró la práctica.");
  const checks = await all<LabCheckRow>(
    db,
    `SELECT position, prompt_markdown, kind, expected_value FROM lab_checks
     WHERE release_id = ?1 AND lab_id = ?2 ORDER BY position`,
    topic.release_id,
    row.id,
  );
  return {
    id: row.id,
    slug: row.slug,
    title: row.title,
    objective_code: row.objective_code,
    objective_title: row.objective_title,
    domain_code: row.domain_code,
    scenario_markdown: row.scenario_markdown,
    setup_sql: row.setup_sql,
    task_markdown: row.task_markdown,
    expected_result: row.expected_result,
    faq: await faqEntries(env, user, topic.release_id, row.id),
    self_check: checks.map(({ expected_value, ...check }) => ({
      ...check,
      hint_available: !["yes", "no", "sí", "si"].includes(
        expected_value.trim().toLocaleLowerCase("es-419"),
      ),
    })),
    passed: Boolean(row.passed),
  };
}

export async function getAbout(env: Env, topicSlug: string): Promise<unknown> {
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  const row = await first<AboutRow>(
    db,
    `SELECT app_version, app_markdown, intake_markdown, sources_markdown,
       content_changes_markdown
     FROM about_documents WHERE release_id = ?1`,
    topic.release_id,
  );
  if (!row) throw new ApiError(503, "content_not_ready", "La información del curso no está disponible.");
  return row;
}

export async function getDashboard(
  env: Env,
  user: AuthorizedUser,
  topicSlug: string,
): Promise<unknown> {
  const topic = await requireTopic(env, topicSlug);
  const db = requireDatabase(env.DB);
  const [domains, objectives, stats, attempts, mastery, labCounts, lastMock] = await Promise.all([
    all<DomainRow>(
      db,
      "SELECT id, code, name, weight_pct FROM domains WHERE release_id = ?1 ORDER BY sort_order",
      topic.release_id,
    ),
    all<ObjectiveRow>(
      db,
      "SELECT id, domain_id, code, title, description FROM objectives WHERE release_id = ?1 ORDER BY sort_order",
      topic.release_id,
    ),
    first<UserStatsRow>(
      db,
      `SELECT xp FROM user_stats WHERE user_id = ?1 AND topic_slug = ?2`,
      user.id,
      topicSlug,
    ),
    all<Record<string, unknown>>(
      db,
      `SELECT a.id, a.attempt_type, a.started_at, a.finished_at, a.score_raw,
        a.score_scaled, a.passed, r.content_version,
        CASE WHEN a.release_id = ?3 THEN 1 ELSE 0 END AS release_active,
        COUNT(aq.question_id) AS total_questions
       FROM attempts a
       JOIN content_releases r ON r.id = a.release_id
       LEFT JOIN attempt_questions aq ON aq.attempt_id = a.id
       WHERE a.user_id = ?1 AND a.topic_slug = ?2
       GROUP BY a.id ORDER BY a.started_at DESC LIMIT 20`,
      user.id,
      topicSlug,
      topic.release_id,
    ),
    all<MasteryRow>(
      db,
      `SELECT objective_id, mastery_pct, due_on FROM mastery
       WHERE user_id = ?1 AND release_id = ?2`,
      user.id,
      topic.release_id,
    ),
    first<{ total: number; passed: number }>(
      db,
      `SELECT COUNT(l.id) AS total,
         COALESCE(SUM(CASE WHEN lp.passed_at IS NULL THEN 0 ELSE 1 END), 0) AS passed
       FROM labs l
       LEFT JOIN lab_progress lp
         ON lp.user_id = ?1 AND lp.release_id = l.release_id AND lp.lab_id = l.id
       WHERE l.release_id = ?2`,
      user.id,
      topic.release_id,
    ),
    first<{ passed: number | null }>(
      db,
      `SELECT passed FROM attempts
       WHERE user_id = ?1 AND release_id = ?2 AND attempt_type = 'mock'
         AND finished_at IS NOT NULL
       ORDER BY finished_at DESC LIMIT 1`,
      user.id,
      topic.release_id,
    ),
  ]);
  const masteryByObjective = new Map(
    mastery.map((row) => [row.objective_id, row]),
  );
  const domainReadiness = domains.map((domain) => {
    const scoped = objectives.filter((objective) => objective.domain_id === domain.id);
    const total = scoped.reduce(
      (sum, objective) => sum + (masteryByObjective.get(objective.id)?.mastery_pct ?? 0),
      0,
    );
    return {
      code: domain.code,
      name: domain.name,
      weight_pct: domain.weight_pct,
      ready_pct: scoped.length ? Math.round(total / scoped.length) : 0,
    };
  });
  const domainWeightTotal = domainReadiness.reduce((sum, domain) => sum + domain.weight_pct, 0);
  const domainReadyPct = domainWeightTotal
    ? Math.round(
        domainReadiness.reduce(
          (sum, domain) => sum + domain.ready_pct * domain.weight_pct,
          0,
        ) / domainWeightTotal,
      )
    : 0;
  const labsPct = labCounts?.total
    ? Math.round((100 * labCounts.passed) / labCounts.total)
    : 0;
  let domainComponentWeight = 70;
  if (!topic.labs_enabled) domainComponentWeight += 20;
  if (!topic.strategy_enabled) domainComponentWeight += 10;
  const overallReadyPct = Math.round(
    (domainReadyPct * domainComponentWeight +
      (topic.labs_enabled ? labsPct * 20 : 0)) /
      100,
  );
  const today = new Date().toISOString().slice(0, 10);
  const reviewQueue = objectives.flatMap((objective) => {
    const row = masteryByObjective.get(objective.id);
    if (!row) {
      return [{ objective_code: objective.code, objective_title: objective.title, status: "new" }];
    }
    if (row.mastery_pct < 100) {
      return [{ objective_code: objective.code, objective_title: objective.title, status: "weak" }];
    }
    if (row.due_on && row.due_on <= today) {
      return [{ objective_code: objective.code, objective_title: objective.title, status: "due" }];
    }
    return [];
  });
  return {
    domain_readiness: domainReadiness,
    domain_ready_pct: domainReadyPct,
    labs_pct: labsPct,
    strategy_pct: 0,
    overall_ready_pct: overallReadyPct,
    exam_ready:
      overallReadyPct >= 80 &&
      (!topic.assessment_enabled || Boolean(lastMock?.passed)),
    xp: stats?.xp ?? 0,
    review_queue: reviewQueue,
    attempt_history: attempts,
    study_plan: objectives.map((objective, index) => ({
      objective_code: objective.code,
      objective_title: objective.title,
      estimated_week: Math.floor(index / 3) + 1,
    })),
  };
}
