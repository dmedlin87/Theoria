CREATE TABLE IF NOT EXISTS agent_trails (
    id TEXT PRIMARY KEY,
    workflow TEXT NOT NULL,
    mode TEXT NULL,
    user_id TEXT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    plan_md TEXT NULL,
    final_md TEXT NULL,
    input_payload JSONB NULL,
    output_payload JSONB NULL,
    error_message TEXT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NULL,
    last_replayed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_steps (
    id TEXT PRIMARY KEY,
    trail_id TEXT NOT NULL REFERENCES agent_trails (id) ON DELETE CASCADE,
    step_index INTEGER NOT NULL,
    tool TEXT NOT NULL,
    action TEXT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    input_payload JSONB NULL,
    output_payload JSONB NULL,
    output_digest TEXT NULL,
    tokens_in INTEGER NULL,
    tokens_out INTEGER NULL,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_agent_steps_trail_order
    ON agent_steps (trail_id, step_index);

CREATE TABLE IF NOT EXISTS trail_sources (
    id TEXT PRIMARY KEY,
    trail_id TEXT NOT NULL REFERENCES agent_trails (id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    reference TEXT NOT NULL,
    meta JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_trail_sources_trail
    ON trail_sources (trail_id);
