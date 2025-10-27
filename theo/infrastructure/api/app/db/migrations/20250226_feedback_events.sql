CREATE TABLE IF NOT EXISTS feedback_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NULL,
    chat_session_id TEXT NULL,
    query TEXT NULL,
    document_id TEXT NULL REFERENCES documents(id) ON DELETE SET NULL,
    passage_id TEXT NULL REFERENCES passages(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK (action IN ('view', 'click', 'copy', 'like', 'dislike')),
    rank INTEGER NULL,
    score DOUBLE PRECISION NULL,
    confidence DOUBLE PRECISION NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_feedback_events_user_created
    ON feedback_events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_feedback_events_session_created
    ON feedback_events (chat_session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_feedback_events_document
    ON feedback_events (document_id);

CREATE INDEX IF NOT EXISTS ix_feedback_events_passage
    ON feedback_events (passage_id);

CREATE INDEX IF NOT EXISTS ix_feedback_events_created_at
    ON feedback_events (created_at DESC);
