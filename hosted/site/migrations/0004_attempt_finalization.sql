PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS attempt_finalizations (
  attempt_id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  xp_awarded INTEGER NOT NULL DEFAULT 0 CHECK (xp_awarded >= 0),
  finalized_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_attempt_finalizations_user
  ON attempt_finalizations(user_id, finalized_at DESC);
