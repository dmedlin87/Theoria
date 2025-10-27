-- Ensure research note tables expose updated_at timestamps used by the MCP tools
-- and create the evidence_cards store consumed by evidence_card_create.

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

ALTER TABLE research_notes
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE research_notes
SET updated_at = created_at
WHERE updated_at IS NULL;

ALTER TABLE research_notes
    ALTER COLUMN updated_at SET NOT NULL,
    ALTER COLUMN updated_at SET DEFAULT NOW();

ALTER TABLE note_evidence
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE note_evidence
SET updated_at = created_at
WHERE updated_at IS NULL;

ALTER TABLE note_evidence
    ALTER COLUMN updated_at SET NOT NULL,
    ALTER COLUMN updated_at SET DEFAULT NOW();
