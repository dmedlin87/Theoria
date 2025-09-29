CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NULL,
    stance TEXT NULL,
    mode_id TEXT NULL,
    summary TEXT NULL,
    memory_snippets JSONB NULL,
    linked_document_ids JSONB NULL,
    preferences JSONB NULL,
    last_turn_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_session_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions (id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations JSONB NULL,
    sequence INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_chat_session_messages_sequence
    ON chat_session_messages (session_id, sequence);

CREATE INDEX IF NOT EXISTS ix_chat_sessions_user
    ON chat_sessions (user_id);
