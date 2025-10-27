ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS goals JSONB NOT NULL DEFAULT '[]'::jsonb;

UPDATE chat_sessions
SET memory_snippets = COALESCE(
    (
        SELECT jsonb_agg(
            jsonb_set(
                jsonb_set(elem, '{goal_id}', COALESCE(elem->'goal_id', 'null'::jsonb), true),
                '{trail_id}',
                COALESCE(elem->'trail_id', 'null'::jsonb),
                true
            )
        )
        FROM jsonb_array_elements(memory_snippets) AS elem
    ),
    '[]'::jsonb
)
WHERE EXISTS (
    SELECT 1
    FROM jsonb_array_elements(memory_snippets) AS elem
    WHERE NOT elem ? 'goal_id' OR NOT elem ? 'trail_id'
);
