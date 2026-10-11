PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS streak_freeze_purchases (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  topic_slug TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  request_fingerprint TEXT NOT NULL,
  xp_after INTEGER NOT NULL DEFAULT 0 CHECK (xp_after >= 0),
  streak_freeze_count_after INTEGER NOT NULL DEFAULT 0 CHECK (streak_freeze_count_after >= 0),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (user_id, idempotency_key),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TRIGGER IF NOT EXISTS trg_streak_freeze_purchase_validate
BEFORE INSERT ON streak_freeze_purchases
BEGIN
  SELECT (CASE
    WHEN NOT EXISTS (
      SELECT 1 FROM user_stats
      WHERE user_id = NEW.user_id AND topic_slug = NEW.topic_slug
        AND xp >= 150 AND streak_freeze_count < 2
    ) THEN RAISE(ABORT, 'streak_freeze_unavailable')
  END);
END;

CREATE TRIGGER IF NOT EXISTS trg_streak_freeze_purchase_apply
AFTER INSERT ON streak_freeze_purchases
BEGIN
  UPDATE user_stats SET
    xp = xp - 150,
    streak_freeze_count = streak_freeze_count + 1
  WHERE user_id = NEW.user_id AND topic_slug = NEW.topic_slug;

  UPDATE streak_freeze_purchases SET
    xp_after = (
      SELECT xp FROM user_stats
      WHERE user_id = NEW.user_id AND topic_slug = NEW.topic_slug
    ),
    streak_freeze_count_after = (
      SELECT streak_freeze_count FROM user_stats
      WHERE user_id = NEW.user_id AND topic_slug = NEW.topic_slug
    )
  WHERE id = NEW.id;
END;
