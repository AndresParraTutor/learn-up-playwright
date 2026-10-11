PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS qa_request_outcomes (
  request_id TEXT PRIMARY KEY,
  outcome TEXT NOT NULL CHECK (outcome IN ('answered', 'insufficient')),
  faq_entry_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (request_id) REFERENCES qa_usage_requests(id) ON DELETE CASCADE,
  FOREIGN KEY (faq_entry_id) REFERENCES faq_entries(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_qa_outcomes_faq
  ON qa_request_outcomes(faq_entry_id);

CREATE TRIGGER IF NOT EXISTS trg_qa_outcome_requires_accepted
BEFORE INSERT ON qa_request_outcomes
BEGIN
  SELECT (CASE
    WHEN NOT EXISTS (
      SELECT 1 FROM qa_usage_requests
      WHERE id = NEW.request_id AND status = 'accepted'
    ) THEN RAISE(ABORT, 'qa_request_not_accepted')
  END);
END;

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
        AND status IN ('reserved', 'accepted', 'ambiguous')
    ) >= (
      SELECT user_max_concurrency FROM usage_policies WHERE id = 'default'
    ) THEN RAISE(ABORT, 'qa_concurrency_exhausted')
  END);
END;

CREATE TRIGGER IF NOT EXISTS trg_qa_reservation_counters
AFTER INSERT ON qa_usage_requests
WHEN NEW.status = 'reserved'
BEGIN
  INSERT INTO usage_counters (scope_key, window_start, credits_used, request_count)
  VALUES (
    'user:' || NEW.user_id || ':minute',
    strftime('%Y-%m-%dT%H:%M:00Z', NEW.created_at),
    NEW.reserved_credits,
    1
  )
  ON CONFLICT(scope_key, window_start) DO UPDATE SET
    credits_used = usage_counters.credits_used + excluded.credits_used,
    request_count = usage_counters.request_count + 1,
    updated_at = CURRENT_TIMESTAMP;

  INSERT INTO usage_counters (scope_key, window_start, credits_used, request_count)
  VALUES (
    'user:' || NEW.user_id || ':day',
    strftime('%Y-%m-%d', NEW.created_at),
    NEW.reserved_credits,
    1
  )
  ON CONFLICT(scope_key, window_start) DO UPDATE SET
    credits_used = usage_counters.credits_used + excluded.credits_used,
    request_count = usage_counters.request_count + 1,
    updated_at = CURRENT_TIMESTAMP;

  INSERT INTO usage_counters (scope_key, window_start, credits_used, request_count)
  VALUES (
    'user:' || NEW.user_id || ':month',
    strftime('%Y-%m-01', NEW.created_at),
    NEW.reserved_credits,
    1
  )
  ON CONFLICT(scope_key, window_start) DO UPDATE SET
    credits_used = usage_counters.credits_used + excluded.credits_used,
    request_count = usage_counters.request_count + 1,
    updated_at = CURRENT_TIMESTAMP;

  INSERT INTO usage_counters (scope_key, window_start, credits_used, request_count)
  VALUES (
    'global:month',
    strftime('%Y-%m-01', NEW.created_at),
    NEW.reserved_credits,
    1
  )
  ON CONFLICT(scope_key, window_start) DO UPDATE SET
    credits_used = usage_counters.credits_used + excluded.credits_used,
    request_count = usage_counters.request_count + 1,
    updated_at = CURRENT_TIMESTAMP;

  SELECT (CASE
    WHEN (
      SELECT request_count FROM usage_counters
      WHERE scope_key = 'user:' || NEW.user_id || ':minute'
        AND window_start = strftime('%Y-%m-%dT%H:%M:00Z', NEW.created_at)
    ) > (
      SELECT user_requests_per_minute FROM usage_policies WHERE id = 'default'
    ) THEN RAISE(ABORT, 'qa_rate_exhausted')
  END);
  SELECT (CASE
    WHEN (
      SELECT credits_used FROM usage_counters
      WHERE scope_key = 'user:' || NEW.user_id || ':day'
        AND window_start = strftime('%Y-%m-%d', NEW.created_at)
    ) > (
      SELECT user_daily_credits FROM usage_policies WHERE id = 'default'
    ) THEN RAISE(ABORT, 'qa_daily_exhausted')
  END);
  SELECT (CASE
    WHEN (
      SELECT credits_used FROM usage_counters
      WHERE scope_key = 'user:' || NEW.user_id || ':month'
        AND window_start = strftime('%Y-%m-01', NEW.created_at)
    ) > (
      SELECT user_monthly_credits FROM usage_policies WHERE id = 'default'
    ) THEN RAISE(ABORT, 'qa_monthly_exhausted')
  END);
  SELECT (CASE
    WHEN (
      SELECT credits_used FROM usage_counters
      WHERE scope_key = 'global:month'
        AND window_start = strftime('%Y-%m-01', NEW.created_at)
    ) > (
      SELECT global_monthly_credits FROM usage_policies WHERE id = 'default'
    ) THEN RAISE(ABORT, 'qa_global_exhausted')
  END);
END;

CREATE TRIGGER IF NOT EXISTS trg_qa_release_local_failure
AFTER UPDATE OF status ON qa_usage_requests
WHEN OLD.status = 'reserved' AND NEW.status = 'failed_local'
BEGIN
  UPDATE usage_counters SET
    credits_used = MAX(0, credits_used - OLD.reserved_credits),
    request_count = MAX(0, request_count - 1),
    updated_at = CURRENT_TIMESTAMP
  WHERE scope_key = 'user:' || OLD.user_id || ':minute'
    AND window_start = strftime('%Y-%m-%dT%H:%M:00Z', OLD.created_at);

  UPDATE usage_counters SET
    credits_used = MAX(0, credits_used - OLD.reserved_credits),
    request_count = MAX(0, request_count - 1),
    updated_at = CURRENT_TIMESTAMP
  WHERE scope_key = 'user:' || OLD.user_id || ':day'
    AND window_start = strftime('%Y-%m-%d', OLD.created_at);

  UPDATE usage_counters SET
    credits_used = MAX(0, credits_used - OLD.reserved_credits),
    request_count = MAX(0, request_count - 1),
    updated_at = CURRENT_TIMESTAMP
  WHERE scope_key = 'user:' || OLD.user_id || ':month'
    AND window_start = strftime('%Y-%m-01', OLD.created_at);

  UPDATE usage_counters SET
    credits_used = MAX(0, credits_used - OLD.reserved_credits),
    request_count = MAX(0, request_count - 1),
    updated_at = CURRENT_TIMESTAMP
  WHERE scope_key = 'global:month'
    AND window_start = strftime('%Y-%m-01', OLD.created_at);
END;
