import { readFile, readdir, stat } from "node:fs/promises";
import { extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const dist = resolve(siteRoot, "dist");
const required = [
  "client/index.html",
  "server/index.js",
  ".openai/hosting.json",
  ".openai/drizzle/0000_content_identity.sql",
  ".openai/drizzle/0001_learning_state.sql",
  ".openai/drizzle/0002_qa_limits.sql",
  ".openai/drizzle/0003_qa_hard_limits.sql",
  ".openai/drizzle/0004_attempt_finalization.sql",
  ".openai/drizzle/0005_qa_recovery.sql",
  ".openai/drizzle/0006_streak_freeze_purchases.sql",
  "server-assets/playwright.seed.json",
  "server-assets/playwright.media.json",
  "server-assets/playwright.seed.sql",
];

for (const relative of required) {
  const value = await stat(resolve(dist, relative)).catch(() => null);
  if (!value?.isFile()) throw new Error(`Missing build artifact: ${relative}`);
}

const seedMigrationNames = (await readdir(resolve(dist, ".openai", "drizzle")))
  .filter((name) => /^0013_playwright_seed_581f525fd95e_\d{3}\.sql$/.test(name))
  .sort();
if (seedMigrationNames.length < 2) throw new Error("Expected split Playwright seed migrations.");
for (const migrationName of seedMigrationNames) {
  const value = await stat(resolve(dist, ".openai", "drizzle", migrationName));
  if (value.size > 16000) throw new Error(`Oversized seed migration: ${migrationName}`);
}

async function filesBelow(root) {
  const result = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = resolve(root, entry.name);
    if (entry.isDirectory()) result.push(...(await filesBelow(path)));
    else if (entry.isFile()) result.push(path);
  }
  return result;
}

const forbiddenNames = new Set([".env", "learn_up.duckdb", "learn_up.duckdb.wal"]);
const forbiddenExtensions = new Set([".mp4", ".pdf", ".map"]);
for (const file of await filesBelow(dist)) {
  const name = file.split(/[\\/]/).at(-1);
  if (name && forbiddenNames.has(name)) throw new Error(`Forbidden artifact: ${file}`);
  if (forbiddenExtensions.has(extname(file).toLowerCase())) {
    throw new Error(`Forbidden artifact type: ${file}`);
  }
}

const clientFiles = await filesBelow(resolve(dist, "client"));
const clientText = (
  await Promise.all(
    clientFiles
      .filter((file) => [".html", ".js", ".css"].includes(extname(file)))
      .map((file) => readFile(file, "utf8")),
  )
).join("\n");

const forbiddenClientValues = [
  "Propósito del testing, QA y defectos",
  "OPENAI_API_KEY",
  "oai-authenticated-user-email",
  "sk-proj-",
  "X-LearnUp-Token",
  "/api/auth/token",
  "Generar video con Gemini Notebook",
];
for (const value of forbiddenClientValues) {
  if (clientText.includes(value)) throw new Error(`Protected value entered client build: ${value}`);
}

const hosting = JSON.parse(await readFile(resolve(dist, ".openai", "hosting.json"), "utf8"));
if (
  !/^appgprj_[a-f0-9]{32}$/.test(hosting.project_id) ||
  hosting.d1 !== "DB" ||
  hosting.r2 !== "BUCKET"
) {
  throw new Error("Unexpected Sites project or storage bindings.");
}

console.log(
  `Sites artifact verified: ${required.length} required files and ${seedMigrationNames.length} seed migrations.`,
);
