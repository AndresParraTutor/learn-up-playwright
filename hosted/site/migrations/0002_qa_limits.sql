PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usage_policies (
  id TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
  current_document_credits INTEGER NOT NULL CHECK (current_document_credits > 0),
  full_source_credits INTEGER NOT NULL CHECK (full_source_credits > 0),
  user_daily_credits INTEGER NOT NULL CHECK (user_daily_credits > 0),
  user_monthly_credits INTEGER NOT NULL CHECK (user_monthly_credits > 0),
  global_monthly_credits INTEGER NOT NULL CHECK (global_monthly_credits > 0),
  user_requests_per_minute INTEGER NOT NULL CHECK (user_requests_per_minute > 0),
  user_max_concurrency INTEGER NOT NULL CHECK (user_max_concurrency > 0),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_counters (
  scope_key TEXT NOT NULL,
  window_start TEXT NOT NULL,
  credits_used INTEGER NOT NULL DEFAULT 0 CHECK (credits_used >= 0),
  request_count INTEGER NOT NULL DEFAULT 0 CHECK (request_count >= 0),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (scope_key, window_start)
);

CREATE TABLE IF NOT EXISTS qa_usage_requests (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  idempotency_key TEXT NOT NULL,
  topic_slug TEXT NOT NULL,
  release_id TEXT NOT NULL,
  content_id TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('current_document', 'full_source')),
  reserved_credits INTEGER NOT NULL CHECK (reserved_credits > 0),
  status TEXT NOT NULL CHECK (status IN ('reserved', 'accepted', 'completed', 'failed_local', 'failed_provider', 'ambiguous')),
  provider_request_id TEXT,
  model TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  accepted_at TEXT,
  finalized_at TEXT,
  UNIQUE (user_id, idempotency_key),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (release_id) REFERENCES content_releases(id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_qa_usage_user_active
  ON qa_usage_requests(user_id)
  WHERE status IN ('reserved', 'accepted', 'ambiguous');

CREATE INDEX IF NOT EXISTS ix_qa_usage_status_created
  ON qa_usage_requests(status, created_at);

CREATE TABLE IF NOT EXISTS operational_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  event_type TEXT NOT NULL,
  subject_id TEXT,
  outcome TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_operational_audit_created
  ON operational_audit(created_at DESC);
