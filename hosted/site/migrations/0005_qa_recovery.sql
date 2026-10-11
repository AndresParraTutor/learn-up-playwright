PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS qa_request_fingerprints (
  request_id TEXT PRIMARY KEY,
  request_fingerprint TEXT NOT NULL,
  FOREIGN KEY (request_id) REFERENCES qa_usage_requests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS qa_reconciliations (
  request_id TEXT PRIMARY KEY,
  owner_user_id INTEGER NOT NULL,
  outcome TEXT NOT NULL CHECK (outcome IN ('confirmed', 'released')),
  idempotency_key TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (owner_user_id, idempotency_key),
  FOREIGN KEY (request_id) REFERENCES qa_usage_requests(id) ON DELETE CASCADE,
  FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE RESTRICT
);

DROP INDEX IF EXISTS uq_qa_usage_user_active;

CREATE UNIQUE INDEX IF NOT EXISTS uq_qa_usage_user_active
  ON qa_usage_requests(user_id)
  WHERE status IN ('reserved', 'accepted');

DROP TRIGGER IF EXISTS trg_qa_reservation_policy;

CREATE TRIGGER IF NOT EXISTS trg_qa_reservation_policy
BEFORE INSERT ON qa_usage_requests
WHEN NEW.status = 'reserved'
BEGIN
  SELECT (CASE
    WHEN NOT EXISTS (
      SELECT 1 FROM usage_policies WHERE id = 'default' AND enabled = 1
    ) THEN RAISE(ABORT, 'qa_disabled')
  END);
  SELECT (CASE
    WHEN NEW.reserved_credits <> (
      SELECT (CASE NEW.mode
        WHEN 'current_document' THEN current_document_credits
        WHEN 'full_source' THEN full_source_credits
      END)
      FROM usage_policies WHERE id = 'default'
    ) THEN RAISE(ABORT, 'qa_credit_mismatch')
  END);
  SELECT (CASE
    WHEN (
      SELECT COUNT(*) FROM qa_usage_requests
      WHERE user_id = NEW.user_id
        AND status IN ('reserved', 'accepted')
    ) >= (
      SELECT user_max_concurrency FROM usage_policies WHERE id = 'default'
    ) THEN RAISE(ABORT, 'qa_concurrency_exhausted')
  END);
END;

CREATE TRIGGER IF NOT EXISTS trg_qa_reconciliation_release
AFTER INSERT ON qa_reconciliations
WHEN NEW.outcome = 'released'
BEGIN
  UPDATE usage_counters SET
    credits_used = MAX(0, credits_used - (
      SELECT reserved_credits FROM qa_usage_requests WHERE id = NEW.request_id
    )),
    request_count = MAX(0, request_count - 1),
    updated_at = CURRENT_TIMESTAMP
  WHERE scope_key = 'user:' || (
      SELECT user_id FROM qa_usage_requests WHERE id = NEW.request_id
    ) || ':minute'
    AND window_start = strftime('%Y-%m-%dT%H:%M:00Z', (
      SELECT created_at FROM qa_usage_requests WHERE id = NEW.request_id
    ));

  UPDATE usage_counters SET
    credits_used = MAX(0, credits_used - (
      SELECT reserved_credits FROM qa_usage_requests WHERE id = NEW.request_id
    )),
    request_count = MAX(0, request_count - 1),
    updated_at = CURRENT_TIMESTAMP
  WHERE scope_key = 'user:' || (
      SELECT user_id FROM qa_usage_requests WHERE id = NEW.request_id
    ) || ':day'
    AND window_start = strftime('%Y-%m-%d', (
      SELECT created_at FROM qa_usage_requests WHERE id = NEW.request_id
    ));

  UPDATE usage_counters SET
    credits_used = MAX(0, credits_used - (
      SELECT reserved_credits FROM qa_usage_requests WHERE id = NEW.request_id
    )),
    request_count = MAX(0, request_count - 1),
    updated_at = CURRENT_TIMESTAMP
  WHERE scope_key = 'user:' || (
      SELECT user_id FROM qa_usage_requests WHERE id = NEW.request_id
    ) || ':month'
    AND window_start = strftime('%Y-%m-01', (
      SELECT created_at FROM qa_usage_requests WHERE id = NEW.request_id
    ));

  UPDATE usage_counters SET
    credits_used = MAX(0, credits_used - (
      SELECT reserved_credits FROM qa_usage_requests WHERE id = NEW.request_id
    )),
    request_count = MAX(0, request_count - 1),
    updated_at = CURRENT_TIMESTAMP
  WHERE scope_key = 'global:month'
    AND window_start = strftime('%Y-%m-01', (
      SELECT created_at FROM qa_usage_requests WHERE id = NEW.request_id
    ));
END;
