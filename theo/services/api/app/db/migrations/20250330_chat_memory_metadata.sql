ALTER TABLE chat_sessions
    ALTER COLUMN memory_snippets TYPE JSONB USING memory_snippets::jsonb;

ALTER TABLE chat_sessions
    ALTER COLUMN memory_snippets SET DEFAULT '[]'::jsonb;
