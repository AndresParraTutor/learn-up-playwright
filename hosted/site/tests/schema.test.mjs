import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { handleRequest, quotaWindows } from "../dist/server/index.js";

const siteRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const migrationsRoot = resolve(siteRoot, "migrations");
const builtMigrationsRoot = resolve(siteRoot, "dist", ".openai", "drizzle");
const seedPath = resolve(siteRoot, "dist", "server-assets", "playwright.seed.sql");

async function applyMigrations(database, passes = 1) {
  const migrationNames = (await readdir(migrationsRoot))
    .filter((name) => name.endsWith(".sql"))
    .sort();
  for (let pass = 0; pass < passes; pass += 1) {
    for (const migrationName of migrationNames) {
      database.exec(await readFile(resolve(migrationsRoot, migrationName), "utf8"));
    }
  }
}

async function applyBuiltMigrations(database, passes = 1) {
  const migrationNames = (await readdir(builtMigrationsRoot))
    .filter((name) => name.endsWith(".sql"))
    .sort();
  for (let pass = 0; pass < passes; pass += 1) {
    for (const migrationName of migrationNames) {
      const migration = await readFile(resolve(builtMigrationsRoot, migrationName), "utf8");
      assert.doesNotMatch(migration, /\r/, `${migrationName} must use LF line endings for remote D1`);
      assert.doesNotMatch(
        migration,
        /SELECT\s+CASE\b/i,
        `${migrationName} must parenthesize CASE expressions inside D1 triggers`,
      );
      const statements = migration
        .split("--> statement-breakpoint")
        .map((statement) => statement.trim())
        .filter(Boolean);
      assert.ok(statements.length > 0, `${migrationName} has no Drizzle statements`);
      for (const statement of statements) database.prepare(statement).run();
    }
  }
}

class SQLiteD1Statement {
  constructor(database, query) {
    this.database = database;
    this.query = query;
    this.values = [];
  }

  bind(...values) {
    this.values = values;
    return this;
  }

  async first(columnName) {
    const row = this.database.prepare(this.query).get(...this.values) ?? null;
    return columnName && row ? row[columnName] ?? null : row;
  }

  async all() {
    return {
      success: true,
      results: this.database.prepare(this.query).all(...this.values),
    };
  }

  async run() {
    const result = this.database.prepare(this.query).run(...this.values);
    return { success: true, results: [], meta: { changes: Number(result.changes) } };
  }
}

class SQLiteD1 {
  constructor(database) {
    this.database = database;
  }

  prepare(query) {
    return new SQLiteD1Statement(this.database, query);
  }

  async batch(statements) {
    this.database.exec("BEGIN TRANSACTION");
    try {
      const results = [];
      for (const statement of statements) results.push(await statement.run());
      this.database.exec("COMMIT");
      return results;
    } catch (error) {
      this.database.exec("ROLLBACK");
      throw error;
    }
  }
}

class FinalizationFailingD1 extends SQLiteD1 {
  async batch(statements) {
    if (statements.some((statement) => statement.query.includes("INSERT INTO faq_entries"))) {
      throw new Error("simulated finalization failure");
    }
    return super.batch(statements);
  }
}

function apiRequest(path, {
  email = "owner@example.test",
  method = "GET",
  body,
  idempotencyKey,
} = {}) {
  const headers = new Headers({
    "oai-authenticated-user-email": email,
    Origin: "https://demo.example",
  });
  if (body !== undefined) headers.set("Content-Type", "application/json");
  if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);
  return new Request(`https://demo.example${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function seededEnvironment() {
  const database = new DatabaseSync(":memory:");
  await applyMigrations(database);
  database.exec(await readFile(seedPath, "utf8"));
  database.exec(`
    INSERT INTO allowlist_entries (normalized_email, role) VALUES
      ('owner@example.test', 'owner'),
      ('partner@example.test', 'learner')
  `);
  const release = database
    .prepare("SELECT source_digest FROM content_releases WHERE status = 'active'")
    .get();
  return {
    database,
    env: {
      DB: new SQLiteD1(database),
      LEARNUP_EXPECTED_CONTENT_DIGEST: release.source_digest,
    },
  };
}

function qaEnvironment(env, overrides = {}) {
  return {
    ...env,
    OPENAI_API_KEY: "test-key-never-log",
    OPENAI_MODEL: "test-model",
    OPENAI_VECTOR_STORE_ID: "vs_test",
    LEARNUP_QA_ENABLED: "true",
    LEARNUP_SAFETY_IDENTIFIER_SALT: "test-salt-at-least-sixteen-characters",
    LEARNUP_QA_CURRENT_CREDITS: "1",
    LEARNUP_QA_FULL_SOURCE_CREDITS: "3",
    LEARNUP_QA_USER_DAILY_CREDITS: "20",
    LEARNUP_QA_USER_MONTHLY_CREDITS: "150",
    LEARNUP_QA_GLOBAL_MONTHLY_CREDITS: "500",
    LEARNUP_QA_USER_REQUESTS_PER_MINUTE: "3",
    LEARNUP_QA_USER_MAX_CONCURRENCY: "1",
    LEARNUP_QA_SELECTION_MAX_CHARS: "3000",
    LEARNUP_QA_QUESTION_MAX_CHARS: "800",
    LEARNUP_QA_MAX_OUTPUT_TOKENS: "700",
    LEARNUP_QA_MAX_RETRIEVAL_RESULTS: "6",
    LEARNUP_QA_MAX_TOOL_CALLS: "1",
    LEARNUP_QA_TIMEOUT_MS: "30000",
    ...overrides,
  };
}

function openAIStream(answer, requestId = "req_test") {
  const completed = {
    type: "response.completed",
    response: {
      id: "resp_test",
      model: "test-model",
      output_text: answer,
      output: [],
      usage: { input_tokens: 20, output_tokens: 8 },
    },
  };
  const payload = [
    `data: ${JSON.stringify({ type: "response.output_text.delta", delta: answer })}`,
    `data: ${JSON.stringify(completed)}`,
    "",
  ].join("\n\n");
  return new Response(payload, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "x-request-id": requestId,
    },
  });
}

test("D1-compatible migrations and deterministic seed are repeatable", async () => {
  const database = new DatabaseSync(":memory:");
  try {
    await applyMigrations(database, 2);

    const seedSql = await readFile(seedPath, "utf8");
    database.exec(seedSql);
    database.exec(seedSql);

    const expectedCounts = {
      content_releases: 1,
      topics: 1,
      domains: 7,
      objectives: 25,
      lessons: 25,
      questions: 75,
      question_choices: 300,
      labs: 25,
      lab_checks: 75,
      mock_exams: 1,
      mock_exam_questions: 50,
      media_objects: 25,
      badges: 2,
    };
    for (const [table, expected] of Object.entries(expectedCounts)) {
      const row = database.prepare(`SELECT COUNT(*) AS count FROM ${table}`).get();
      assert.equal(row.count, expected, `unexpected row count for ${table}`);
    }

    const active = database
      .prepare("SELECT COUNT(*) AS count FROM content_releases WHERE status = 'active'")
      .get();
    assert.equal(active.count, 1);
    assert.deepEqual(database.prepare("PRAGMA foreign_key_check").all(), []);
  } finally {
    database.close();
  }
});

test("built Drizzle migrations are complete single statements and repeatable", async () => {
  const database = new DatabaseSync(":memory:");
  try {
    await applyBuiltMigrations(database, 2);
    assert.deepEqual(database.prepare("PRAGMA foreign_key_check").all(), []);
    const triggers = database
      .prepare("SELECT COUNT(*) AS count FROM sqlite_master WHERE type = 'trigger'")
      .get();
    assert.equal(triggers.count, 7);
    const activeRelease = database
      .prepare("SELECT source_digest FROM content_releases WHERE status = 'active'")
      .get();
    assert.equal(
      activeRelease.source_digest,
      "581f525fd95e2dd7cf3ca19f865c9652cf91f547e83efc086deec653ac450172",
    );
    assert.equal(database.prepare("SELECT COUNT(*) AS count FROM lessons").get().count, 25);
    assert.equal(database.prepare("SELECT COUNT(*) AS count FROM questions").get().count, 75);
  } finally {
    database.close();
  }
});

test("Sites v1 schema upgrades without rewriting its published Q&A migration", async () => {
  const database = new DatabaseSync(":memory:");
  try {
    const published = await readFile(resolve(migrationsRoot, "0002_qa_limits.sql"), "utf8");
    assert.doesNotMatch(published, /request_fingerprint/);
    for (const name of ["0000_content_identity.sql", "0001_learning_state.sql", "0002_qa_limits.sql"]) {
      database.exec(await readFile(resolve(migrationsRoot, name), "utf8"));
    }
    assert.equal(
      database.prepare("SELECT COUNT(*) AS count FROM pragma_table_info('qa_usage_requests') WHERE name = 'request_fingerprint'").get().count,
      0,
    );
    for (let pass = 0; pass < 2; pass += 1) {
      for (const name of [
        "0003_qa_hard_limits.sql",
        "0004_attempt_finalization.sql",
        "0005_qa_recovery.sql",
        "0006_streak_freeze_purchases.sql",
      ]) {
        database.exec(await readFile(resolve(migrationsRoot, name), "utf8"));
      }
    }
    assert.equal(database.prepare("SELECT COUNT(*) AS count FROM pragma_table_info('qa_request_fingerprints')").get().count, 2);
    assert.equal(database.prepare("SELECT COUNT(*) AS count FROM pragma_table_info('qa_reconciliations')").get().count, 5);
    assert.equal(database.prepare("SELECT COUNT(*) AS count FROM pragma_table_info('streak_freeze_purchases')").get().count, 8);
  } finally {
    database.close();
  }
});

test("seeded catalog routes satisfy the hosted read contract", async () => {
  const database = new DatabaseSync(":memory:");
  try {
    await applyMigrations(database);
    database.exec(await readFile(seedPath, "utf8"));
    database
      .prepare("INSERT INTO allowlist_entries (normalized_email, role) VALUES (?1, 'owner')")
      .run("owner@example.test");

    const release = database
      .prepare("SELECT source_digest FROM content_releases WHERE status = 'active'")
      .get();
    const env = {
      DB: new SQLiteD1(database),
      LEARNUP_EXPECTED_CONTENT_DIGEST: release.source_digest,
    };
    const headers = { "oai-authenticated-user-email": "owner@example.test" };
    const get = async (path) => {
      const response = await handleRequest(
        new Request(`https://demo.example${path}`, { headers }),
        env,
      );
      assert.equal(response.status, 200, `${path} returned ${response.status}`);
      return response.json();
    };

    const topics = await get("/api/topics");
    assert.equal(topics.length, 1);
    assert.equal(topics[0].objective_count, 25);

    const wrongRelease = await handleRequest(
      new Request("https://demo.example/api/topics", { headers }),
      { ...env, LEARNUP_EXPECTED_CONTENT_DIGEST: "0".repeat(64) },
    );
    assert.equal(wrongRelease.status, 503);
    assert.equal((await wrongRelease.json()).code, "content_not_ready");

    const topic = await get("/api/topics/playwright");
    assert.equal(topic.syllabus_version, "v1");

    const domains = await get("/api/t/playwright/domains");
    assert.equal(domains.length, 7);
    assert.equal(domains.reduce((total, domain) => total + domain.objectives.length, 0), 25);

    const lessons = await get("/api/t/playwright/lessons");
    assert.equal(lessons.length, 25);
    const lesson = await get("/api/t/playwright/lessons/proposito-testing-qa-defectos");
    assert.equal(lesson.objective_code, "1.1");
    assert.deepEqual(lesson.faq, []);

    const labs = await get("/api/t/playwright/labs");
    assert.equal(labs.length, 25);
    const lab = await get("/api/t/playwright/labs/clasificar-evidencia-y-defectos");
    assert.equal(lab.self_check.length, 3);

    const dashboard = await get("/api/t/playwright/progress/dashboard");
    assert.equal(dashboard.domain_readiness.length, 7);
    assert.equal(dashboard.review_queue.length, 25);

    const about = await get("/api/t/playwright/about");
    assert.equal(about.app_version, "1.15");
  } finally {
    database.close();
  }
});

test("hosted learning mutations persist per user and enforce attempt ownership", async () => {
  const { database, env } = await seededEnvironment();
  try {
    const create = await handleRequest(
      apiRequest("/api/t/playwright/attempts", {
        method: "POST",
        body: { attempt_type: "practice", objective_code: "1.1", question_count: 2 },
      }),
      env,
    );
    assert.equal(create.status, 201);
    const attempt = await create.json();
    assert.equal(attempt.questions.length, 2);

    const foreign = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${attempt.id}`, {
        email: "partner@example.test",
      }),
      env,
    );
    assert.equal(foreign.status, 404);

    const question = attempt.questions[0];
    const correctChoices = database
      .prepare(
        `SELECT id FROM question_choices
         WHERE question_id = ?1 AND correct = 1 ORDER BY position`,
      )
      .all(question.question_id)
      .map((row) => row.id);
    const owner = database.prepare("SELECT id FROM users WHERE normalized_email = 'owner@example.test'").get();
    database.prepare("INSERT OR IGNORE INTO user_stats (user_id, topic_slug) VALUES (?1, 'playwright')").run(owner.id);
    database.prepare(
      "UPDATE user_stats SET current_streak = 7, longest_streak = 12, streak_freeze_count = 2, last_activity_on = '2020-01-01' WHERE user_id = ?1",
    ).run(owner.id);
    const answered = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${attempt.id}/responses`, {
        method: "POST",
        body: {
          question_id: question.question_id,
          selected_choice_ids: correctChoices,
        },
      }),
      env,
    );
    assert.equal(answered.status, 200);
    const responseResult = await answered.json();
    assert.equal(responseResult.is_correct, true);
    assert.equal(responseResult.xp_awarded, 10);
    assert.equal(responseResult.badges_earned[0].code, "first-attempt");
    assert.deepEqual(
      { ...database.prepare("SELECT current_streak, longest_streak, streak_freeze_count, last_activity_on FROM user_stats WHERE user_id = ?1").get(owner.id) },
      { current_streak: 7, longest_streak: 12, streak_freeze_count: 2, last_activity_on: "2020-01-01" },
    );

    const duplicate = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${attempt.id}/responses`, {
        method: "POST",
        body: {
          question_id: question.question_id,
          selected_choice_ids: correctChoices,
        },
      }),
      env,
    );
    assert.equal(duplicate.status, 409);

    const finish = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${attempt.id}/finish`, { method: "POST" }),
      env,
    );
    assert.equal(finish.status, 200);
    assert.equal((await finish.json()).score_raw, 1);

    const review = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${attempt.id}/review`),
      env,
    );
    assert.equal(review.status, 200);
    assert.equal((await review.json()).questions[0].is_correct, true);

    const labSlug = "clasificar-evidencia-y-defectos";
    const answers = database
      .prepare(
        `SELECT lc.expected_value
         FROM lab_checks lc JOIN labs l
           ON l.release_id = lc.release_id AND l.id = lc.lab_id
         WHERE l.slug = ?1 ORDER BY lc.position`,
      )
      .all(labSlug)
      .map((row) => row.expected_value);
    const checked = await handleRequest(
      apiRequest(`/api/t/playwright/labs/${labSlug}/check`, {
        method: "POST",
        body: { answers },
      }),
      env,
    );
    assert.equal(checked.status, 200);
    assert.equal((await checked.json()).passed, true);

    const ownerLab = await handleRequest(
      apiRequest(`/api/t/playwright/labs/${labSlug}`),
      env,
    );
    assert.equal((await ownerLab.json()).passed, true);
    const partnerLab = await handleRequest(
      apiRequest(`/api/t/playwright/labs/${labSlug}`, {
        email: "partner@example.test",
      }),
      env,
    );
    assert.equal((await partnerLab.json()).passed, false);

    const dashboard = await handleRequest(
      apiRequest("/api/t/playwright/progress/dashboard"),
      env,
    );
    const dashboardBody = await dashboard.json();
    assert.equal(dashboardBody.xp, 10);
    assert.ok(dashboardBody.domain_ready_pct > 0);
    assert.ok(dashboardBody.labs_pct > 0);
  } finally {
    database.close();
  }
});

test("finished attempts remain reviewable after a content release changes", async () => {
  const { database, env } = await seededEnvironment();
  try {
    const createAttempt = async () => {
      const response = await handleRequest(
        apiRequest("/api/t/playwright/attempts", {
          method: "POST",
          body: { attempt_type: "practice", objective_code: "1.1", question_count: 1 },
        }),
        env,
      );
      assert.equal(response.status, 201);
      return response.json();
    };
    const finished = await createAttempt();
    const unfinished = await createAttempt();
    const finish = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${finished.id}/finish`, { method: "POST" }),
      env,
    );
    assert.equal(finish.status, 200);

    const oldRelease = database.prepare("SELECT * FROM content_releases WHERE status = 'active'").get();
    const oldTopic = database.prepare("SELECT * FROM topics WHERE release_id = ?1").get(oldRelease.id);
    database.prepare("UPDATE content_releases SET status = 'retired' WHERE id = ?1").run(oldRelease.id);
    const newReleaseId = "playwright-release-v2";
    const newDigest = "f".repeat(64);
    database.prepare(
      `INSERT INTO content_releases
       (id, topic_slug, content_version, source_digest, status, activated_at)
       VALUES (?1, 'playwright', 'v2', ?2, 'active', CURRENT_TIMESTAMP)`,
    ).run(newReleaseId, newDigest);
    database.prepare(
      `INSERT INTO topics
       (release_id, id, slug, name, description, content_version, content_language,
        assessment_enabled, assessment_question_count, assessment_minutes,
        assessment_scoring, pass_pct, pass_score_scaled, max_score_scaled,
        penalty_for_wrong_answers, labs_enabled, strategy_enabled)
       VALUES (?1, ?2, ?3, ?4, ?5, 'v2', ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16)`,
    ).run(
      newReleaseId, oldTopic.id, oldTopic.slug, oldTopic.name, oldTopic.description,
      oldTopic.content_language, oldTopic.assessment_enabled, oldTopic.assessment_question_count,
      oldTopic.assessment_minutes, oldTopic.assessment_scoring, oldTopic.pass_pct,
      oldTopic.pass_score_scaled, oldTopic.max_score_scaled, oldTopic.penalty_for_wrong_answers,
      oldTopic.labs_enabled, oldTopic.strategy_enabled,
    );
    env.LEARNUP_EXPECTED_CONTENT_DIGEST = newDigest;

    const review = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${finished.id}/review`),
      env,
    );
    assert.equal(review.status, 200);
    assert.equal((await review.json()).content_version, oldRelease.content_version);
    const retired = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${unfinished.id}`),
      env,
    );
    assert.equal(retired.status, 409);
    assert.equal((await retired.json()).code, "attempt_release_retired");
    const dashboard = await handleRequest(apiRequest("/api/t/playwright/progress/dashboard"), env);
    const history = (await dashboard.json()).attempt_history;
    assert.equal(history.find((row) => row.id === finished.id).release_active, 0);
    const foreign = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${finished.id}/review`, { email: "partner@example.test" }),
      env,
    );
    assert.equal(foreign.status, 404);
  } finally {
    database.close();
  }
});

test("Playwright disables mocks and keeps every module drill", async () => {
  const { database, env } = await seededEnvironment();
  try {
    const topic = await handleRequest(apiRequest("/api/topics/playwright"), env);
    assert.equal(topic.status, 200);
    assert.equal((await topic.json()).assessment_enabled, false);
    const dashboard = await handleRequest(apiRequest("/api/t/playwright/progress/dashboard"), env);
    assert.ok(!Object.keys(await dashboard.json()).some((key) => key.includes("streak")));
    const retiredCodes = ["streak-3", "streak-7", "mock-pass", "exam-ready"];
    const owner = database.prepare("SELECT id FROM users WHERE normalized_email = 'owner@example.test'").get();
    for (const code of retiredCodes) {
      database.prepare("INSERT INTO badges (code, name, description, icon) VALUES (?1, 'Legacy', 'Legacy', '')").run(code);
      database.prepare("INSERT INTO user_badges (user_id, badge_code) VALUES (?1, ?2)").run(owner.id, code);
    }
    const badges = await handleRequest(apiRequest("/api/t/playwright/progress/badges"), env);
    const visibleBadges = await badges.json();
    assert.ok(visibleBadges.every((badge) => !retiredCodes.includes(badge.code)));
    assert.deepEqual(visibleBadges.map((badge) => badge.code), ["clean-sweep", "first-attempt"]);
    const purchase = await handleRequest(
      apiRequest("/api/t/playwright/progress/streak-freeze", { method: "POST" }), env,
    );
    assert.equal(purchase.status, 404);
    const mock = await handleRequest(
      apiRequest("/api/t/playwright/attempts", {
        method: "POST",
        body: { attempt_type: "mock" },
      }),
      env,
    );
    assert.equal(mock.status, 400);
    for (let domain = 1; domain <= 7; domain += 1) {
      const drill = await handleRequest(
        apiRequest("/api/t/playwright/attempts", {
          method: "POST",
          body: { attempt_type: "domain_drill", domain_code: String(domain) },
        }),
        env,
      );
      assert.equal(drill.status, 201);
      assert.ok((await drill.json()).questions.length > 0);
    }
  } finally {
    database.close();
  }
});

test("a perfect legacy mock awards no badges", async () => {
  const { database, env } = await seededEnvironment();
  try {
    database.prepare("UPDATE topics SET assessment_enabled = 1 WHERE slug = 'playwright'").run();
    const created = await handleRequest(
      apiRequest("/api/t/playwright/attempts", { method: "POST", body: { attempt_type: "mock" } }), env,
    );
    assert.equal(created.status, 201);
    const attempt = await created.json();
    database.exec(`INSERT INTO responses (attempt_id, release_id, question_id, is_correct)
      SELECT attempt_id, release_id, question_id, 1 FROM attempt_questions WHERE attempt_id = ${attempt.id}`);
    const finished = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${attempt.id}/finish`, { method: "POST" }), env,
    );
    assert.equal(finished.status, 200);
    const result = await finished.json();
    assert.equal(result.passed, true);
    assert.deepEqual(result.badges_earned, []);
    assert.equal(database.prepare("SELECT COUNT(*) AS count FROM user_badges").get().count, 0);
  } finally {
    database.close();
  }
});

test("the fixed final assessment is timed server-side and finalization is idempotent", async () => {
  const { database, env } = await seededEnvironment();
  try {
    database.prepare("UPDATE topics SET assessment_enabled = 1 WHERE slug = 'playwright'").run();
    const created = await handleRequest(
      apiRequest("/api/t/playwright/attempts", {
        method: "POST",
        body: { attempt_type: "mock" },
      }),
      env,
    );
    assert.equal(created.status, 201);
    const attempt = await created.json();
    assert.equal(attempt.questions.length, 50);
    assert.equal(attempt.minutes_allowed, 60);
    const earlyReview = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${attempt.id}/review`),
      env,
    );
    assert.equal(earlyReview.status, 409);
    assert.equal((await earlyReview.json()).code, "attempt_not_finished");

    const firstQuestion = attempt.questions[0];
    const firstChoices = database
      .prepare("SELECT id FROM question_choices WHERE question_id = ?1 AND correct = 1 ORDER BY position")
      .all(firstQuestion.question_id);
    const recorded = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${attempt.id}/responses`, {
        method: "POST",
        body: {
          question_id: firstQuestion.question_id,
          selected_choice_ids: firstChoices.map(({ id }) => id),
        },
      }),
      env,
    );
    assert.equal(recorded.status, 200);
    assert.deepEqual(await recorded.json(), {
      question_id: firstQuestion.question_id,
      recorded: true,
      is_correct: null,
      explanation_markdown: null,
      choices: [],
      xp_awarded: 0,
      badges_earned: [],
    });
    database
      .prepare("UPDATE attempts SET started_at = ?1 WHERE id = ?2")
      .run("2020-01-01T00:00:00.000Z", attempt.id);

    const question = attempt.questions[1];
    const choice = database
      .prepare("SELECT id FROM question_choices WHERE question_id = ?1 AND correct = 1 LIMIT 1")
      .get(question.question_id);
    const late = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${attempt.id}/responses`, {
        method: "POST",
        body: {
          question_id: question.question_id,
          selected_choice_ids: [choice.id],
        },
      }),
      env,
    );
    assert.equal(late.status, 409);
    assert.equal((await late.json()).code, "attempt_time_expired");

    const firstFinish = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${attempt.id}/finish`, { method: "POST" }),
      env,
    );
    assert.equal(firstFinish.status, 200);
    const firstResult = await firstFinish.json();
    assert.equal(firstResult.total_questions, 50);
    assert.equal(firstResult.score_raw, 1);
    assert.equal(firstResult.score_scaled, 2);
    assert.equal(firstResult.passed, false);

    const secondFinish = await handleRequest(
      apiRequest(`/api/t/playwright/attempts/${attempt.id}/finish`, { method: "POST" }),
      env,
    );
    assert.equal(secondFinish.status, 200);
    assert.deepEqual(
      { ...(await secondFinish.json()), badges_earned: [] },
      { ...firstResult, badges_earned: [] },
    );
    assert.equal(
      database.prepare("SELECT COUNT(*) AS count FROM attempt_finalizations").get().count,
      1,
    );
  } finally {
    database.close();
  }
});

test("contextual Q&A stays disabled or fails closed before reserving paid usage", async () => {
  const { database, env } = await seededEnvironment();
  try {
    const quota = await handleRequest(apiRequest("/api/t/playwright/quota"), env);
    assert.deepEqual(await quota.json(), { enabled: false });
    const path = "/api/t/playwright/lessons/proposito-testing-qa-defectos/questions";
    const body = {
      selected_text: "Automatizar pruebas no empieza con una herramienta.",
      question: "¿Por qué?",
      use_full_sources: false,
    };
    const disabled = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-disabled-request-01",
      }),
      env,
    );
    assert.equal(disabled.status, 503);
    assert.equal((await disabled.json()).code, "qa_disabled");

    const misconfigured = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-misconfigured-001",
      }),
      { ...env, LEARNUP_QA_ENABLED: "true" },
    );
    assert.equal(misconfigured.status, 503);
    assert.equal((await misconfigured.json()).code, "qa_configuration_invalid");
    assert.equal(database.prepare("SELECT COUNT(*) AS count FROM qa_usage_requests").get().count, 0);
  } finally {
    database.close();
  }
});

test("contextual Q&A streams, charges once, isolates FAQs, and supports deletion", async () => {
  const { database, env: baseEnv } = await seededEnvironment();
  const env = qaEnvironment(baseEnv);
  const originalFetch = globalThis.fetch;
  const upstreamBodies = [];
  let calls = 0;
  globalThis.fetch = async (_url, init) => {
    calls += 1;
    upstreamBodies.push(JSON.parse(init.body));
    return openAIStream("El testing aporta evidencia para tomar decisiones.", `req_${calls}`);
  };
  try {
    const path = "/api/t/playwright/lessons/proposito-testing-qa-defectos/questions";
    const body = {
      selected_text: "Automatizar pruebas no empieza con una herramienta.",
      question: "¿Qué significa esta idea?",
      use_full_sources: false,
    };
    const first = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-current-00000001",
      }),
      env,
    );
    assert.equal(first.status, 200);
    const stream = await first.text();
    assert.match(stream, /"type":"delta"/);
    assert.match(stream, /"type":"result"/);
    assert.equal(calls, 1);
    assert.equal(upstreamBodies[0].store, false);
    assert.equal(upstreamBodies[0].max_output_tokens, 700);
    assert.equal(upstreamBodies[0].safety_identifier.length, 64);
    assert.doesNotMatch(upstreamBodies[0].safety_identifier, /owner@example\.test/);
    assert.match(upstreamBodies[0].instructions, /INSUFFICIENT_CONTEXT/);
    assert.match(upstreamBodies[0].instructions, /datos no confiables/);
    assert.equal(upstreamBodies[0].tools, undefined);

    const replay = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-current-00000001",
      }),
      env,
    );
    assert.equal(replay.status, 200);
    assert.match(await replay.text(), /"type":"result"/);
    assert.equal(calls, 1);

    const mismatchedReplay = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body: { ...body, question: "Explicalo de otra manera." },
        idempotencyKey: "qa-current-00000001",
      }),
      env,
    );
    assert.equal(mismatchedReplay.status, 409);
    assert.equal((await mismatchedReplay.json()).code, "idempotency_key_reused");
    assert.equal(calls, 1);

    const ownerLesson = await handleRequest(
      apiRequest("/api/t/playwright/lessons/proposito-testing-qa-defectos"),
      env,
    );
    assert.equal((await ownerLesson.json()).faq.length, 1);
    const partnerLesson = await handleRequest(
      apiRequest("/api/t/playwright/lessons/proposito-testing-qa-defectos", {
        email: "partner@example.test",
      }),
      env,
    );
    assert.deepEqual((await partnerLesson.json()).faq, []);

    const quota = await handleRequest(
      apiRequest("/api/t/playwright/quota"),
      env,
    );
    const quotaBody = await quota.json();
    assert.equal(quotaBody.daily.used, 1);
    assert.equal(quotaBody.monthly.used, 1);
    const partnerQuota = await handleRequest(
      apiRequest("/api/t/playwright/quota", { email: "partner@example.test" }),
      env,
    );
    assert.equal((await partnerQuota.json()).daily.used, 0);

    const full = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body: { ...body, use_full_sources: true },
        idempotencyKey: "qa-full-source-0001",
      }),
      env,
    );
    assert.equal(full.status, 200);
    await full.text();
    assert.deepEqual(upstreamBodies[1].tools, [{
      type: "file_search",
      vector_store_ids: ["vs_test"],
      max_num_results: 6,
    }]);
    assert.equal(upstreamBodies[1].max_tool_calls, 1);

    const remove = await handleRequest(
      apiRequest("/api/t/playwright/lessons/proposito-testing-qa-defectos/faq/0", {
        method: "DELETE",
      }),
      env,
    );
    assert.equal(remove.status, 204);
    const afterDelete = await handleRequest(
      apiRequest("/api/t/playwright/lessons/proposito-testing-qa-defectos"),
      env,
    );
    assert.equal((await afterDelete.json()).faq.length, 1);
    assert.equal(
      database.prepare("SELECT COUNT(*) AS count FROM faq_entries").get().count,
      1,
    );
  } finally {
    globalThis.fetch = originalFetch;
    database.close();
  }
});

test("Q&A quota reservations are atomic under concurrency and fail closed", async () => {
  const { database, env: baseEnv } = await seededEnvironment();
  const env = qaEnvironment(baseEnv);
  const originalFetch = globalThis.fetch;
  let releaseFetch;
  let signalStarted;
  const started = new Promise((resolve) => { signalStarted = resolve; });
  const pending = new Promise((resolve) => { releaseFetch = resolve; });
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    signalStarted();
    return pending;
  };
  try {
    const path = "/api/t/playwright/lessons/proposito-testing-qa-defectos/questions";
    const body = {
      selected_text: "Automatizar pruebas no empieza con una herramienta.",
      question: "¿Por qué?",
      use_full_sources: false,
    };
    const firstPromise = handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-concurrent-00001",
      }),
      env,
    );
    await started;
    const second = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-concurrent-00002",
      }),
      env,
    );
    assert.equal(second.status, 409);
    assert.equal((await second.json()).code, "qa_concurrency_exhausted");
    assert.equal(calls, 1);

    releaseFetch(openAIStream("Porque orienta la investigación del riesgo."));
    const first = await firstPromise;
    assert.equal(first.status, 200);
    await first.text();

    globalThis.fetch = async () => {
      calls += 1;
      throw new TypeError("simulated network ambiguity");
    };
    const ambiguous = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-ambiguous-00001",
      }),
      env,
    );
    assert.equal(ambiguous.status, 502);
    assert.equal((await ambiguous.json()).code, "qa_provider_ambiguous");
    globalThis.fetch = async () => {
      calls += 1;
      return openAIStream("Porque el estado ambiguo ya no ocupa concurrencia.", "req_after_ambiguous");
    };
    const afterAmbiguous = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-after-ambiguous",
      }),
      env,
    );
    assert.equal(afterAmbiguous.status, 200);
    await afterAmbiguous.text();

    const ledger = database
      .prepare("SELECT status, reserved_credits FROM qa_usage_requests ORDER BY created_at")
      .all();
    assert.deepEqual(ledger.map((row) => row.status), ["completed", "ambiguous", "completed"]);
    assert.equal(
      database.prepare("SELECT SUM(credits_used) AS used FROM usage_counters WHERE scope_key LIKE '%:day'").get().used,
      3,
    );
    const learnerList = await handleRequest(
      apiRequest("/api/admin/qa/ambiguous", { email: "partner@example.test" }),
      env,
    );
    assert.equal(learnerList.status, 403);
    const ownerList = await handleRequest(apiRequest("/api/admin/qa/ambiguous"), env);
    const ambiguousRows = await ownerList.json();
    assert.equal(ambiguousRows.length, 1);
    assert.equal(ambiguousRows[0].reconciliation_outcome, null);
    const reconciliationPath = `/api/admin/qa/ambiguous/${ambiguousRows[0].id}/reconcile`;
    const reconcile = await handleRequest(
      apiRequest(reconciliationPath, {
        method: "POST",
        body: { outcome: "released" },
        idempotencyKey: "qa-reconcile-release-01",
      }),
      env,
    );
    assert.deepEqual(await reconcile.json(), {
      request_id: ambiguousRows[0].id,
      outcome: "released",
      replayed: false,
    });
    const reconcileReplay = await handleRequest(
      apiRequest(reconciliationPath, {
        method: "POST",
        body: { outcome: "released" },
        idempotencyKey: "qa-reconcile-release-01",
      }),
      env,
    );
    assert.equal((await reconcileReplay.json()).replayed, true);
    assert.equal(
      database.prepare("SELECT SUM(credits_used) AS used FROM usage_counters WHERE scope_key LIKE '%:day'").get().used,
      2,
    );
  } finally {
    globalThis.fetch = originalFetch;
    database.close();
  }
});

test("Q&A rejects cross-document selections before charging and enforces the global cap", async () => {
  const { database, env: baseEnv } = await seededEnvironment();
  const env = qaEnvironment(baseEnv, { LEARNUP_QA_GLOBAL_MONTHLY_CREDITS: "1" });
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return openAIStream("INSUFFICIENT_CONTEXT");
  };
  try {
    const path = "/api/t/playwright/lessons/proposito-testing-qa-defectos/questions";
    const invalid = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body: {
          selected_text: "Este texto no existe en ninguna parte de la lección.",
          question: "¿Qué significa?",
          use_full_sources: false,
        },
        idempotencyKey: "qa-invalid-scope-001",
      }),
      env,
    );
    assert.equal(invalid.status, 400);
    assert.equal((await invalid.json()).code, "selection_out_of_scope");
    assert.equal(calls, 0);
    assert.equal(database.prepare("SELECT COUNT(*) AS count FROM qa_usage_requests").get().count, 0);

    const body = {
      selected_text: "Automatizar pruebas no empieza con una herramienta.",
      question: "¿Qué significa?",
      use_full_sources: false,
    };
    const first = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-global-first-0001",
      }),
      env,
    );
    assert.equal(first.status, 200);
    assert.match(await first.text(), /"type":"insufficient"/);
    assert.equal(database.prepare("SELECT COUNT(*) AS count FROM faq_entries").get().count, 0);

    const exhausted = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-global-second-001",
      }),
      env,
    );
    assert.equal(exhausted.status, 503);
    assert.equal((await exhausted.json()).code, "qa_global_exhausted");
    assert.equal(calls, 1);
    assert.equal(database.prepare("SELECT COUNT(*) AS count FROM qa_usage_requests").get().count, 1);
  } finally {
    globalThis.fetch = originalFetch;
    database.close();
  }
});

test("Q&A stream failures and client cancellation become terminal ambiguity", async () => {
  const { database, env: baseEnv } = await seededEnvironment();
  const env = qaEnvironment(baseEnv);
  const originalFetch = globalThis.fetch;
  const path = "/api/t/playwright/lessons/proposito-testing-qa-defectos/questions";
  const body = {
    selected_text: "Automatizar pruebas no empieza con una herramienta.",
    question: "¿Por qué?",
    use_full_sources: false,
  };
  try {
    globalThis.fetch = async () => new Response("data: not-json\n\n", { status: 200 });
    const invalid = await handleRequest(
      apiRequest(path, { method: "POST", body, idempotencyKey: "qa-invalid-stream-01" }),
      env,
    );
    assert.equal(invalid.status, 200);
    await invalid.text();

    globalThis.fetch = async () => new Response(
      new ReadableStream({ start() {} }),
      { status: 200, headers: { "x-request-id": "req_cancelled" } },
    );
    const cancelled = await handleRequest(
      apiRequest(path, { method: "POST", body, idempotencyKey: "qa-client-cancel-0001" }),
      env,
    );
    assert.equal(cancelled.status, 200);
    await cancelled.body.cancel();

    env.DB = new FinalizationFailingD1(database);
    globalThis.fetch = async () => openAIStream("Respuesta que no podrá persistirse.", "req_persist");
    const persistenceFailure = await handleRequest(
      apiRequest(path, { method: "POST", body, idempotencyKey: "qa-persist-fail-0001" }),
      env,
    );
    assert.equal(persistenceFailure.status, 200);
    await persistenceFailure.text();

    const rows = database.prepare(
      "SELECT status, finalized_at FROM qa_usage_requests ORDER BY created_at",
    ).all();
    assert.deepEqual(rows.map((row) => row.status), ["ambiguous", "ambiguous", "ambiguous"]);
    assert.ok(rows.every((row) => row.finalized_at));
    const quota = await handleRequest(apiRequest("/api/t/playwright/quota"), env);
    assert.equal((await quota.json()).active_requests, 0);
  } finally {
    globalThis.fetch = originalFetch;
    database.close();
  }
});

test("an explicit provider rejection is charged, recorded, and releases concurrency", async () => {
  const { database, env: baseEnv } = await seededEnvironment();
  const env = qaEnvironment(baseEnv);
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    if (calls === 1) {
      return new Response('{"error":{"message":"rate limited"}}', {
        status: 429,
        headers: { "x-request-id": "req_rejected" },
      });
    }
    return openAIStream("El contexto permite responder.", "req_recovered");
  };
  try {
    const path = "/api/t/playwright/lessons/proposito-testing-qa-defectos/questions";
    const body = {
      selected_text: "Automatizar pruebas no empieza con una herramienta.",
      question: "¿Por qué?",
      use_full_sources: false,
    };
    const rejected = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-provider-reject-01",
      }),
      env,
    );
    assert.equal(rejected.status, 429);
    assert.equal((await rejected.json()).code, "qa_provider_limited");

    const rejectedReplay = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-provider-reject-01",
      }),
      env,
    );
    assert.equal(rejectedReplay.status, 409);
    assert.equal((await rejectedReplay.json()).code, "qa_request_failed");
    assert.equal(calls, 1);

    const recovered = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-provider-recover-1",
      }),
      env,
    );
    assert.equal(recovered.status, 200);
    await recovered.text();

    const requests = database
      .prepare(
        `SELECT status, provider_request_id
         FROM qa_usage_requests ORDER BY created_at, id`,
      )
      .all();
    assert.deepEqual(requests.map((row) => row.status), ["failed_provider", "completed"]);
    assert.equal(requests[0].provider_request_id, "req_rejected");
    assert.equal(
      database
        .prepare("SELECT credits_used FROM usage_counters WHERE scope_key LIKE '%:day'")
        .get().credits_used,
      2,
    );
  } finally {
    globalThis.fetch = originalFetch;
    database.close();
  }
});

test("the per-user request rate is enforced before a fourth provider call", async () => {
  const { database, env: baseEnv } = await seededEnvironment();
  const env = qaEnvironment(baseEnv);
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return openAIStream("INSUFFICIENT_CONTEXT", `req_rate_${calls}`);
  };
  try {
    const path = "/api/t/playwright/lessons/proposito-testing-qa-defectos/questions";
    const body = {
      selected_text: "Automatizar pruebas no empieza con una herramienta.",
      question: "¿Por qué?",
      use_full_sources: false,
    };
    for (let index = 0; index < 3; index += 1) {
      const response = await handleRequest(
        apiRequest(path, {
          method: "POST",
          body,
          idempotencyKey: `qa-rate-allowed-${index}`,
        }),
        env,
      );
      assert.equal(response.status, 200);
      await response.text();
    }
    const limited = await handleRequest(
      apiRequest(path, {
        method: "POST",
        body,
        idempotencyKey: "qa-rate-limited-0001",
      }),
      env,
    );
    assert.equal(limited.status, 429);
    assert.equal((await limited.json()).code, "qa_rate_exhausted");
    assert.equal(calls, 3);
  } finally {
    globalThis.fetch = originalFetch;
    database.close();
  }
});

test("mutation requests reject cross-site origins before changing learner state", async () => {
  const { database, env } = await seededEnvironment();
  try {
    const request = apiRequest("/api/t/playwright/attempts", {
      method: "POST",
      body: { attempt_type: "quick_drill" },
    });
    request.headers.set("Origin", "https://attacker.example");
    request.headers.set("Sec-Fetch-Site", "cross-site");
    const response = await handleRequest(request, env);
    assert.equal(response.status, 403);
    assert.equal((await response.json()).code, "cross_site_denied");
    assert.equal(database.prepare("SELECT COUNT(*) AS count FROM attempts").get().count, 0);
  } finally {
    database.close();
  }
});

test("quota windows roll over on UTC minute, day, and month boundaries", () => {
  const windows = quotaWindows(new Date("2026-12-31T23:59:59.900Z"));
  assert.equal(windows.minute, "2026-12-31T23:59:00Z");
  assert.equal(windows.day, "2026-12-31");
  assert.equal(windows.month, "2026-12-01");
  assert.equal(windows.nextMinute, "2027-01-01T00:00:00.000Z");
  assert.equal(windows.nextDay, "2027-01-01T00:00:00.000Z");
  assert.equal(windows.nextMonth, "2027-01-01T00:00:00.000Z");
});
