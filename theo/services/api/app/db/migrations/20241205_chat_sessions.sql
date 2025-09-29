CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NULL,
    stance TEXT NULL,
    summary TEXT NULL,
    memory_snippets JSONB NOT NULL DEFAULT '[]'::jsonb,
    document_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    preferences JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_interaction_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chat_sessions_updated_at
    ON chat_sessions (updated_at DESC);

CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_updated
    ON chat_sessions (user_id, updated_at DESC);
