ALTER TABLE research_notes
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE research_notes
SET updated_at = created_at;

ALTER TABLE note_evidence
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE note_evidence
SET updated_at = created_at;
