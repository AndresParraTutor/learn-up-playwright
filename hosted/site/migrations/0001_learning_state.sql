PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS user_stats (
  user_id INTEGER NOT NULL,
  topic_slug TEXT NOT NULL,
  xp INTEGER NOT NULL DEFAULT 0 CHECK (xp >= 0),
  current_streak INTEGER NOT NULL DEFAULT 0 CHECK (current_streak >= 0),
  longest_streak INTEGER NOT NULL DEFAULT 0 CHECK (longest_streak >= 0),
  streak_freeze_count INTEGER NOT NULL DEFAULT 0 CHECK (streak_freeze_count >= 0),
  last_activity_on TEXT,
  PRIMARY KEY (user_id, topic_slug),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lesson_progress (
  user_id INTEGER NOT NULL,
  release_id TEXT NOT NULL,
  lesson_id TEXT NOT NULL,
  completed_at TEXT,
  last_opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, release_id, lesson_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (release_id, lesson_id) REFERENCES lessons(release_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS mastery (
  user_id INTEGER NOT NULL,
  release_id TEXT NOT NULL,
  objective_id TEXT NOT NULL,
  mastery_pct REAL NOT NULL DEFAULT 0 CHECK (mastery_pct >= 0 AND mastery_pct <= 100),
  due_on TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, release_id, objective_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (release_id, objective_id) REFERENCES objectives(release_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS lab_progress (
  user_id INTEGER NOT NULL,
  release_id TEXT NOT NULL,
  lab_id TEXT NOT NULL,
  attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  last_checked_at TEXT,
  passed_at TEXT,
  PRIMARY KEY (user_id, release_id, lab_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (release_id, lab_id) REFERENCES labs(release_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS badges (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  icon TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_badges (
  user_id INTEGER NOT NULL,
  badge_code TEXT NOT NULL,
  earned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, badge_code),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (badge_code) REFERENCES badges(code) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  release_id TEXT NOT NULL,
  topic_slug TEXT NOT NULL,
  attempt_type TEXT NOT NULL CHECK (attempt_type IN ('practice', 'domain_drill', 'quick_drill', 'mock')),
  label TEXT NOT NULL,
  minutes_allowed INTEGER,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  score_raw INTEGER,
  score_scaled INTEGER,
  passed INTEGER CHECK (passed IN (0, 1)),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (release_id) REFERENCES content_releases(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS attempt_questions (
  attempt_id INTEGER NOT NULL,
  release_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  PRIMARY KEY (attempt_id, position),
  UNIQUE (attempt_id, question_id),
  FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
  FOREIGN KEY (release_id, question_id) REFERENCES questions(release_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS responses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_id INTEGER NOT NULL,
  release_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
  answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (attempt_id, question_id),
  FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
  FOREIGN KEY (release_id, question_id) REFERENCES questions(release_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS response_choices (
  response_id INTEGER NOT NULL,
  release_id TEXT NOT NULL,
  choice_id TEXT NOT NULL,
  PRIMARY KEY (response_id, choice_id),
  FOREIGN KEY (response_id) REFERENCES responses(id) ON DELETE CASCADE,
  FOREIGN KEY (release_id, choice_id) REFERENCES question_choices(release_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS faq_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  release_id TEXT NOT NULL,
  content_id TEXT NOT NULL,
  display_index INTEGER NOT NULL,
  question TEXT NOT NULL,
  selected_text TEXT,
  answer_markdown TEXT NOT NULL,
  source_references_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (user_id, release_id, content_id, display_index),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (release_id) REFERENCES content_releases(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_mastery_user_due ON mastery(user_id, due_on);
CREATE INDEX IF NOT EXISTS ix_attempts_user_topic_started ON attempts(user_id, topic_slug, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_faq_user_content ON faq_entries(user_id, release_id, content_id, created_at);
