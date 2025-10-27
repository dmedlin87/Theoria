CREATE TABLE IF NOT EXISTS creator_verse_rollups (
    id TEXT PRIMARY KEY,
    osis TEXT NOT NULL,
    creator_id TEXT NOT NULL REFERENCES creators (id) ON DELETE CASCADE,
    stance_counts JSONB NULL,
    avg_confidence DOUBLE PRECISION NULL,
    claim_count INTEGER NOT NULL DEFAULT 0,
    top_quote_ids JSONB NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_creator_verse_rollups_osis
    ON creator_verse_rollups (osis);

CREATE INDEX IF NOT EXISTS ix_creator_verse_rollups_creator
    ON creator_verse_rollups (creator_id);
