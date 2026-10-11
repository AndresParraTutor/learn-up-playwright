import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(siteRoot, "..", "..");
const seed = JSON.parse(
  await readFile(resolve(repoRoot, "hosted", "generated", "playwright.seed.json"), "utf8"),
);
const media = JSON.parse(
  await readFile(resolve(repoRoot, "hosted", "generated", "playwright.media.json"), "utf8"),
);

function sql(value) {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "boolean") return value ? "1" : "0";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("Non-finite number in hosted seed.");
    return String(value);
  }
  return `'${String(value).replaceAll("'", "''")}'`;
}

const maxTextStatementBytes = 1000;

function textChunks(value, maxBytes = maxTextStatementBytes) {
  const chunks = [];
  let chunk = "";
  let chunkBytes = 0;
  for (const character of value) {
    const characterBytes = Buffer.byteLength(character, "utf8");
    if (chunkBytes + characterBytes > maxBytes) {
      chunks.push(chunk);
      chunk = "";
      chunkBytes = 0;
    }
    chunk += character;
    chunkBytes += characterBytes;
  }
  if (chunk) chunks.push(chunk);
  return chunks;
}

function upsert(table, columns, keyColumns, row) {
  const chunkedColumns = columns.filter(
    (column) =>
      typeof row[column] === "string" &&
      Buffer.byteLength(row[column], "utf8") > maxTextStatementBytes,
  );
  const values = columns
    .map((column) => sql(chunkedColumns.includes(column) ? "" : row[column]))
    .join(", ");
  const updates = columns
    .filter((column) => !keyColumns.includes(column))
    .map((column) => `${column} = excluded.${column}`)
    .join(", ");
  const statements = [
    `INSERT INTO ${table} (${columns.join(", ")}) VALUES (${values})\nON CONFLICT (${keyColumns.join(", ")}) DO UPDATE SET ${updates};`,
  ];
  const where = keyColumns.map((column) => `${column} = ${sql(row[column])}`).join(" AND ");
  for (const column of chunkedColumns) {
    for (const chunk of textChunks(row[column])) {
      statements.push(`UPDATE ${table} SET ${column} = ${column} || ${sql(chunk)} WHERE ${where};`);
    }
  }
  return statements.join("\n\n");
}

const releaseId = `release:${seed.source_tree_sha256}`;
const topic = seed.topic;
const badges = [
  ["first-attempt", "Primer intento", "Completaste tu primera respuesta.", "🧭"],
  ["clean-sweep", "Recorrido perfecto", "Lograste un intento sin errores.", "✨"],
];
const statements = [
  "PRAGMA foreign_keys = ON;",
  "BEGIN TRANSACTION;",
  `INSERT INTO content_releases (id, topic_slug, content_version, source_digest, status)\nVALUES (${sql(releaseId)}, ${sql(topic.slug)}, ${sql(topic.content_version)}, ${sql(seed.source_tree_sha256)}, 'staging')\nON CONFLICT (id) DO NOTHING;`,
];

for (const [code, name, description, icon] of badges) {
  statements.push(upsert(
    "badges",
    ["code", "name", "description", "icon"],
    ["code"],
    { code, name, description, icon },
  ));
}

statements.push(upsert(
  "topics",
  ["release_id", "id", "slug", "name", "description", "content_version", "content_language", "assessment_enabled", "assessment_question_count", "assessment_minutes", "assessment_scoring", "pass_pct", "pass_score_scaled", "max_score_scaled", "penalty_for_wrong_answers", "labs_enabled", "strategy_enabled"],
  ["release_id", "id"],
  {
    release_id: releaseId,
    id: topic.id,
    slug: topic.slug,
    name: topic.name,
    description: topic.description,
    content_version: topic.content_version,
    content_language: topic.content_language,
    assessment_enabled: topic.assessment.enabled,
    assessment_question_count: topic.assessment.question_count,
    assessment_minutes: topic.assessment.minutes,
    assessment_scoring: topic.assessment.scoring,
    pass_pct: topic.assessment.pass_pct,
    pass_score_scaled: topic.assessment.pass_score_scaled,
    max_score_scaled: topic.assessment.max_score_scaled,
    penalty_for_wrong_answers: topic.assessment.penalty_for_wrong_answers,
    labs_enabled: topic.modules.labs,
    strategy_enabled: topic.modules.strategy,
  },
));

let objectiveOrder = 0;
for (const [domainIndex, domain] of seed.domains.entries()) {
  statements.push(upsert(
    "domains",
    ["release_id", "id", "topic_id", "code", "name", "weight_pct", "sort_order"],
    ["release_id", "id"],
    { release_id: releaseId, id: domain.id, topic_id: domain.topic_id, code: domain.code, name: domain.name, weight_pct: domain.weight_pct, sort_order: domainIndex },
  ));
  for (const objective of domain.objectives) {
    statements.push(upsert(
      "objectives",
      ["release_id", "id", "domain_id", "code", "title", "description", "sort_order"],
      ["release_id", "id"],
      { release_id: releaseId, id: objective.id, domain_id: objective.domain_id, code: objective.code, title: objective.title, description: objective.topics.join(" · "), sort_order: objectiveOrder++ },
    ));
  }
}

for (const [index, lesson] of seed.lessons.entries()) {
  statements.push(upsert(
    "lessons",
    ["release_id", "id", "objective_id", "slug", "title", "body_markdown", "why_it_matters_markdown", "video_object_key", "sort_order"],
    ["release_id", "id"],
    { release_id: releaseId, id: lesson.id, objective_id: lesson.objective_id, slug: lesson.slug, title: lesson.title, body_markdown: lesson.body_markdown, why_it_matters_markdown: lesson.why_it_matters_markdown, video_object_key: lesson.video_object_key, sort_order: index },
  ));
}

for (const [index, question] of seed.questions.entries()) {
  statements.push(upsert(
    "questions",
    ["release_id", "id", "objective_id", "external_id", "question_type", "stem_markdown", "explanation_markdown", "difficulty", "mock_eligible", "sort_order"],
    ["release_id", "id"],
    { release_id: releaseId, id: question.id, objective_id: question.objective_id, external_id: question.external_id, question_type: question.type, stem_markdown: question.stem_markdown, explanation_markdown: question.explanation_markdown, difficulty: question.difficulty, mock_eligible: question.mock_eligible, sort_order: index },
  ));
  for (const choice of question.choices) {
    statements.push(upsert(
      "question_choices",
      ["release_id", "id", "question_id", "position", "text_markdown", "correct", "explanation_markdown"],
      ["release_id", "id"],
      { release_id: releaseId, id: choice.id, question_id: question.id, position: choice.position, text_markdown: choice.text_markdown, correct: choice.correct, explanation_markdown: choice.explanation_markdown },
    ));
  }
}

for (const [index, lab] of seed.labs.entries()) {
  statements.push(upsert(
    "labs",
    ["release_id", "id", "objective_id", "slug", "title", "scenario_markdown", "setup_sql", "task_markdown", "expected_result", "sort_order"],
    ["release_id", "id"],
    { release_id: releaseId, id: lab.id, objective_id: lab.objective_id, slug: lab.slug, title: lab.title, scenario_markdown: lab.scenario_markdown, setup_sql: lab.setup_sql, task_markdown: lab.task_markdown, expected_result: lab.expected_result, sort_order: index },
  ));
  for (const check of lab.self_check) {
    statements.push(upsert(
      "lab_checks",
      ["release_id", "id", "lab_id", "position", "prompt_markdown", "kind", "expected_value", "case_sensitive"],
      ["release_id", "id"],
      { release_id: releaseId, id: check.id, lab_id: lab.id, position: check.position, prompt_markdown: check.prompt_markdown, kind: check.kind, expected_value: check.expected_value, case_sensitive: check.case_sensitive },
    ));
  }
}

for (const mock of seed.mocks) {
  statements.push(upsert(
    "mock_exams",
    ["release_id", "id", "topic_id", "code"],
    ["release_id", "id"],
    { release_id: releaseId, id: mock.id, topic_id: mock.topic_id, code: mock.code },
  ));
  for (const [position, questionId] of mock.question_ids.entries()) {
    statements.push(upsert(
      "mock_exam_questions",
      ["release_id", "mock_id", "question_id", "position"],
      ["release_id", "mock_id", "position"],
      { release_id: releaseId, mock_id: mock.id, question_id: questionId, position },
    ));
  }
}

for (const object of media.objects) {
  statements.push(upsert(
    "media_objects",
    ["release_id", "content_id", "object_key", "content_type", "byte_size", "sha256", "available"],
    ["release_id", "content_id"],
    { release_id: releaseId, content_id: object.content_id, object_key: object.object_key, content_type: object.content_type, byte_size: object.bytes, sha256: object.sha256, available: object.available },
  ));
}

statements.push(upsert(
  "about_documents",
  ["release_id", "app_version", "app_markdown", "intake_markdown", "sources_markdown", "content_changes_markdown"],
  ["release_id"],
  { release_id: releaseId, app_version: seed.about.app_version, app_markdown: seed.about.app_markdown, intake_markdown: seed.about.intake_markdown, sources_markdown: seed.about.sources_markdown, content_changes_markdown: seed.about.content_changes_markdown },
));

statements.push(
  "CREATE TEMP TABLE _learnup_seed_assertion (value INTEGER NOT NULL CHECK (value = 1));",
  `INSERT INTO _learnup_seed_assertion(value) SELECT (CASE WHEN
    (SELECT COUNT(*) FROM domains WHERE release_id = ${sql(releaseId)}) = ${sql(seed.counts.domains)} AND
    (SELECT COUNT(*) FROM objectives WHERE release_id = ${sql(releaseId)}) = ${sql(seed.counts.objectives)} AND
    (SELECT COUNT(*) FROM lessons WHERE release_id = ${sql(releaseId)}) = ${sql(seed.counts.lessons)} AND
    (SELECT COUNT(*) FROM questions WHERE release_id = ${sql(releaseId)}) = ${sql(seed.counts.questions)} AND
    (SELECT COUNT(*) FROM labs WHERE release_id = ${sql(releaseId)}) = ${sql(seed.counts.labs)} AND
    (SELECT COUNT(*) FROM mock_exams WHERE release_id = ${sql(releaseId)}) = ${sql(seed.counts.mocks)}
    THEN 1 ELSE 0 END);`,
  "DROP TABLE _learnup_seed_assertion;",
  `UPDATE content_releases SET status = 'retired'
   WHERE topic_slug = ${sql(topic.slug)} AND status = 'active' AND id <> ${sql(releaseId)};`,
  `UPDATE content_releases SET status = 'active', activated_at = COALESCE(activated_at, CURRENT_TIMESTAMP)
   WHERE id = ${sql(releaseId)};`,
  "COMMIT;",
  "",
);

const output = resolve(siteRoot, "dist", "server-assets", "playwright.seed.sql");
await mkdir(dirname(output), { recursive: true });
await writeFile(output, statements.join("\n\n"), "utf8");
console.log(`Generated ${output}`);
