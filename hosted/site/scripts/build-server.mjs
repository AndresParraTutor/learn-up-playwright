import { cp, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const siteRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(siteRoot, "..", "..");
const dist = resolve(siteRoot, "dist");
const execFileAsync = promisify(execFile);

await mkdir(resolve(dist, "server"), { recursive: true });
await build({
  entryPoints: [resolve(siteRoot, "src", "server", "index.ts")],
  outfile: resolve(dist, "server", "index.js"),
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "es2022",
  sourcemap: false,
  legalComments: "none",
  minify: false,
});

await mkdir(resolve(dist, ".openai", "drizzle"), { recursive: true });
await cp(
  resolve(siteRoot, ".openai", "hosting.json"),
  resolve(dist, ".openai", "hosting.json"),
);

await mkdir(resolve(dist, "server-assets"), { recursive: true });
await cp(
  resolve(repoRoot, "hosted", "generated", "playwright.seed.json"),
  resolve(dist, "server-assets", "playwright.seed.json"),
);
await cp(
  resolve(repoRoot, "hosted", "generated", "playwright.media.json"),
  resolve(dist, "server-assets", "playwright.media.json"),
);
await execFileAsync(process.execPath, [resolve(siteRoot, "scripts", "build-seed-sql.mjs")], {
  cwd: siteRoot,
});

function drizzleStatements(sql, fileName) {
  const statements = [];
  let start = 0;
  let word = "";
  let currentWords = [];
  let triggerDepth = 0;
  let triggerStatement = false;
  let quote = null;
  let lineComment = false;
  let blockComment = false;

  const acceptWord = () => {
    if (!word) return;
    const upper = word.toUpperCase();
    currentWords.push(upper);
    if (currentWords.length === 2) {
      triggerStatement = currentWords[0] === "CREATE" && currentWords[1] === "TRIGGER";
    }
    if (triggerStatement) {
      if (upper === "BEGIN" || upper === "CASE") triggerDepth += 1;
      else if (upper === "END") triggerDepth -= 1;
      if (triggerDepth < 0) throw new Error(`Unbalanced trigger blocks in ${fileName}`);
    }
    word = "";
  };

  for (let index = 0; index < sql.length; index += 1) {
    const character = sql[index];
    const next = sql[index + 1];

    if (lineComment) {
      if (character === "\n") lineComment = false;
      continue;
    }
    if (blockComment) {
      if (character === "*" && next === "/") {
        blockComment = false;
        index += 1;
      }
      continue;
    }
    if (quote) {
      if (character === quote) {
        if (next === quote) index += 1;
        else quote = null;
      }
      continue;
    }
    if (character === "-" && next === "-") {
      acceptWord();
      lineComment = true;
      index += 1;
      continue;
    }
    if (character === "/" && next === "*") {
      acceptWord();
      blockComment = true;
      index += 1;
      continue;
    }
    if (character === "'" || character === '"' || character === "`") {
      acceptWord();
      quote = character;
      continue;
    }
    if (/[A-Za-z_]/.test(character)) {
      word += character;
      continue;
    }

    acceptWord();
    if (character !== ";" || (triggerStatement && triggerDepth > 0)) continue;

    const statement = sql.slice(start, index + 1).trim();
    if (statement) statements.push(statement);
    start = index + 1;
    currentWords = [];
    triggerDepth = 0;
    triggerStatement = false;
  }

  acceptWord();
  const trailing = sql.slice(start).trim();
  if (quote || blockComment || triggerDepth !== 0 || trailing) {
    throw new Error(`Incomplete SQL statement in ${fileName}`);
  }
  return statements;
}

const migrationsRoot = resolve(siteRoot, "migrations");
for (const migrationName of (await readdir(migrationsRoot)).filter((name) => name.endsWith(".sql")).sort()) {
  const source = (await readFile(resolve(migrationsRoot, migrationName), "utf8")).replace(/\r\n?/g, "\n");
  const statements = drizzleStatements(source, migrationName);
  if (statements.length === 0) throw new Error(`Empty migration: ${migrationName}`);
  await writeFile(
    resolve(dist, ".openai", "drizzle", migrationName),
    `${statements.join("\n\n--> statement-breakpoint\n\n")}\n`,
    "utf8",
  );
}

const seedMigrationSequence = "0013";
const expectedSeedDigest = "581f525fd95e2dd7cf3ca19f865c9652cf91f547e83efc086deec653ac450172";
const seedData = JSON.parse(
  await readFile(resolve(dist, "server-assets", "playwright.seed.json"), "utf8"),
);
if (seedData.source_tree_sha256 !== expectedSeedDigest) {
  throw new Error(
    "The Playwright content digest changed; append a new immutable seed migration sequence.",
  );
}

const seedMigrationPrefix = `${seedMigrationSequence}_playwright_seed_${expectedSeedDigest.slice(0, 12)}`;
const seedSource = await readFile(resolve(dist, "server-assets", "playwright.seed.sql"), "utf8");
const seedStatements = drizzleStatements(seedSource, `${seedMigrationPrefix}.sql`).filter(
  (statement) =>
    !/^(?:PRAGMA foreign_keys = ON|BEGIN TRANSACTION|COMMIT);$/i.test(statement) &&
    !/^(?:CREATE TEMP TABLE|INSERT INTO|DROP TABLE) _learnup_seed_assertion\b/i.test(statement),
);
const seedMigrationMaxBytes = 16000;
const seedMigrationGroups = [];
let seedMigrationGroup = [];
let seedMigrationBytes = 0;
for (const statement of seedStatements) {
  const statementBytes = Buffer.byteLength(statement, "utf8");
  if (statementBytes > seedMigrationMaxBytes) {
    throw new Error(`Seed statement exceeds ${seedMigrationMaxBytes} bytes`);
  }
  const separatorBytes = seedMigrationGroup.length > 0
    ? Buffer.byteLength("\n\n--> statement-breakpoint\n\n")
    : 0;
  if (
    seedMigrationGroup.length > 0 &&
    seedMigrationBytes + separatorBytes + statementBytes > seedMigrationMaxBytes
  ) {
    seedMigrationGroups.push(seedMigrationGroup);
    seedMigrationGroup = [];
    seedMigrationBytes = 0;
  }
  seedMigrationGroup.push(statement);
  seedMigrationBytes += (seedMigrationGroup.length > 1 ? separatorBytes : 0) + statementBytes;
}
if (seedMigrationGroup.length > 0) seedMigrationGroups.push(seedMigrationGroup);

for (const [index, group] of seedMigrationGroups.entries()) {
  const migrationName = `${seedMigrationPrefix}_${String(index + 1).padStart(3, "0")}.sql`;
  await writeFile(
    resolve(dist, ".openai", "drizzle", migrationName),
    `${group.join("\n\n--> statement-breakpoint\n\n")}\n`,
    "utf8",
  );
}
