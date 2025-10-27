CREATE TABLE IF NOT EXISTS trail_retrieval_snapshots (
    id TEXT PRIMARY KEY,
    trail_id TEXT NOT NULL REFERENCES agent_trails (id) ON DELETE CASCADE,
    step_id TEXT NULL REFERENCES agent_steps (id) ON DELETE SET NULL,
    turn_index INTEGER NOT NULL,
    retrieval_hash TEXT NOT NULL,
    passage_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    osis_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_trail_retrieval_turn
    ON trail_retrieval_snapshots (trail_id, turn_index);

CREATE INDEX IF NOT EXISTS ix_trail_retrieval_trail
    ON trail_retrieval_snapshots (trail_id);

CREATE INDEX IF NOT EXISTS ix_trail_retrieval_hash
    ON trail_retrieval_snapshots (retrieval_hash);
