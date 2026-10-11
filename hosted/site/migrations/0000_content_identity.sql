PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS content_releases (
  id TEXT PRIMARY KEY,
  topic_slug TEXT NOT NULL,
  content_version TEXT NOT NULL,
  source_digest TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('staging', 'active', 'retired')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  activated_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_content_releases_active_topic
  ON content_releases(topic_slug) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS topics (
  release_id TEXT NOT NULL,
  id TEXT NOT NULL,
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  content_version TEXT NOT NULL,
  content_language TEXT NOT NULL,
  assessment_enabled INTEGER NOT NULL CHECK (assessment_enabled IN (0, 1)),
  assessment_question_count INTEGER NOT NULL,
  assessment_minutes INTEGER NOT NULL,
  assessment_scoring TEXT NOT NULL,
  pass_pct INTEGER,
  pass_score_scaled INTEGER,
  max_score_scaled INTEGER,
  penalty_for_wrong_answers INTEGER NOT NULL CHECK (penalty_for_wrong_answers IN (0, 1)),
  labs_enabled INTEGER NOT NULL CHECK (labs_enabled IN (0, 1)),
  strategy_enabled INTEGER NOT NULL CHECK (strategy_enabled IN (0, 1)),
  PRIMARY KEY (release_id, id),
  UNIQUE (release_id, slug),
  FOREIGN KEY (release_id) REFERENCES content_releases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS domains (
  release_id TEXT NOT NULL,
  id TEXT NOT NULL,
  topic_id TEXT NOT NULL,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  weight_pct INTEGER NOT NULL CHECK (weight_pct >= 0 AND weight_pct <= 100),
  sort_order INTEGER NOT NULL,
  PRIMARY KEY (release_id, id),
  UNIQUE (release_id, topic_id, code),
  FOREIGN KEY (release_id, topic_id) REFERENCES topics(release_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS objectives (
  release_id TEXT NOT NULL,
  id TEXT NOT NULL,
  domain_id TEXT NOT NULL,
  code TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  sort_order INTEGER NOT NULL,
  PRIMARY KEY (release_id, id),
  UNIQUE (release_id, code),
  FOREIGN KEY (release_id, domain_id) REFERENCES domains(release_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lessons (
  release_id TEXT NOT NULL,
  id TEXT NOT NULL,
  objective_id TEXT NOT NULL,
  slug TEXT NOT NULL,
  title TEXT NOT NULL,
  body_markdown TEXT NOT NULL,
  why_it_matters_markdown TEXT NOT NULL,
  video_object_key TEXT,
  sort_order INTEGER NOT NULL,
  PRIMARY KEY (release_id, id),
  UNIQUE (release_id, slug),
  FOREIGN KEY (release_id, objective_id) REFERENCES objectives(release_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS questions (
  release_id TEXT NOT NULL,
  id TEXT NOT NULL,
  objective_id TEXT NOT NULL,
  external_id TEXT NOT NULL,
  question_type TEXT NOT NULL CHECK (question_type IN ('single', 'multi')),
  stem_markdown TEXT NOT NULL,
  explanation_markdown TEXT NOT NULL,
  difficulty INTEGER NOT NULL,
  mock_eligible INTEGER NOT NULL CHECK (mock_eligible IN (0, 1)),
  sort_order INTEGER NOT NULL,
  PRIMARY KEY (release_id, id),
  UNIQUE (release_id, external_id),
  FOREIGN KEY (release_id, objective_id) REFERENCES objectives(release_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS question_choices (
  release_id TEXT NOT NULL,
  id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  text_markdown TEXT NOT NULL,
  correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
  explanation_markdown TEXT NOT NULL,
  PRIMARY KEY (release_id, id),
  UNIQUE (release_id, question_id, position),
  FOREIGN KEY (release_id, question_id) REFERENCES questions(release_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS labs (
  release_id TEXT NOT NULL,
  id TEXT NOT NULL,
  objective_id TEXT NOT NULL,
  slug TEXT NOT NULL,
  title TEXT NOT NULL,
  scenario_markdown TEXT NOT NULL,
  setup_sql TEXT NOT NULL,
  task_markdown TEXT NOT NULL,
  expected_result TEXT NOT NULL,
  sort_order INTEGER NOT NULL,
  PRIMARY KEY (release_id, id),
  UNIQUE (release_id, slug),
  FOREIGN KEY (release_id, objective_id) REFERENCES objectives(release_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lab_checks (
  release_id TEXT NOT NULL,
  id TEXT NOT NULL,
  lab_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  prompt_markdown TEXT NOT NULL,
  kind TEXT NOT NULL,
  expected_value TEXT NOT NULL,
  case_sensitive INTEGER NOT NULL CHECK (case_sensitive IN (0, 1)),
  PRIMARY KEY (release_id, id),
  UNIQUE (release_id, lab_id, position),
  FOREIGN KEY (release_id, lab_id) REFERENCES labs(release_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mock_exams (
  release_id TEXT NOT NULL,
  id TEXT NOT NULL,
  topic_id TEXT NOT NULL,
  code TEXT NOT NULL,
  PRIMARY KEY (release_id, id),
  UNIQUE (release_id, code),
  FOREIGN KEY (release_id, topic_id) REFERENCES topics(release_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mock_exam_questions (
  release_id TEXT NOT NULL,
  mock_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  PRIMARY KEY (release_id, mock_id, position),
  UNIQUE (release_id, mock_id, question_id),
  FOREIGN KEY (release_id, mock_id) REFERENCES mock_exams(release_id, id) ON DELETE CASCADE,
  FOREIGN KEY (release_id, question_id) REFERENCES questions(release_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS media_objects (
  release_id TEXT NOT NULL,
  content_id TEXT NOT NULL,
  object_key TEXT NOT NULL,
  content_type TEXT NOT NULL,
  byte_size INTEGER,
  sha256 TEXT,
  available INTEGER NOT NULL CHECK (available IN (0, 1)),
  PRIMARY KEY (release_id, content_id),
  UNIQUE (release_id, object_key),
  FOREIGN KEY (release_id) REFERENCES content_releases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS about_documents (
  release_id TEXT PRIMARY KEY,
  app_version TEXT NOT NULL,
  app_markdown TEXT NOT NULL,
  intake_markdown TEXT NOT NULL,
  sources_markdown TEXT NOT NULL,
  content_changes_markdown TEXT NOT NULL,
  FOREIGN KEY (release_id) REFERENCES content_releases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  normalized_email TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS allowlist_entries (
  normalized_email TEXT PRIMARY KEY,
  role TEXT NOT NULL CHECK (role IN ('owner', 'learner')),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_domains_release_order ON domains(release_id, sort_order);
CREATE INDEX IF NOT EXISTS ix_objectives_release_order ON objectives(release_id, sort_order);
CREATE INDEX IF NOT EXISTS ix_lessons_release_order ON lessons(release_id, sort_order);
CREATE INDEX IF NOT EXISTS ix_questions_release_order ON questions(release_id, sort_order);
CREATE INDEX IF NOT EXISTS ix_labs_release_order ON labs(release_id, sort_order);
CREATE INDEX IF NOT EXISTS ix_media_objects_key ON media_objects(release_id, object_key);
