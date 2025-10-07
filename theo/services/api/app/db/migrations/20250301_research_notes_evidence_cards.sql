ALTER TABLE research_notes
    ADD COLUMN IF NOT EXISTS stance TEXT NULL,
    ADD COLUMN IF NOT EXISTS claim_type TEXT NULL,
    ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NULL,
    ADD COLUMN IF NOT EXISTS tags JSONB NULL,
    ADD COLUMN IF NOT EXISTS request_id TEXT NULL,
    ADD COLUMN IF NOT EXISTS created_by TEXT NULL,
    ADD COLUMN IF NOT EXISTS tenant_id TEXT NULL;

CREATE INDEX IF NOT EXISTS ix_research_notes_request_id
    ON research_notes (request_id);

CREATE INDEX IF NOT EXISTS ix_research_notes_created_by
    ON research_notes (created_by);

CREATE INDEX IF NOT EXISTS ix_research_notes_tenant_id
    ON research_notes (tenant_id);

CREATE TABLE IF NOT EXISTS evidence_cards (
    id TEXT PRIMARY KEY,
    osis TEXT NOT NULL,
    claim_summary TEXT NOT NULL,
    evidence JSONB NOT NULL,
    tags JSONB NULL,
    request_id TEXT NULL,
    created_by TEXT NULL,
    tenant_id TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_evidence_cards_osis
    ON evidence_cards (osis);

CREATE INDEX IF NOT EXISTS ix_evidence_cards_request_id
    ON evidence_cards (request_id);

CREATE INDEX IF NOT EXISTS ix_evidence_cards_created_by
    ON evidence_cards (created_by);

CREATE INDEX IF NOT EXISTS ix_evidence_cards_tenant_id
    ON evidence_cards (tenant_id);
