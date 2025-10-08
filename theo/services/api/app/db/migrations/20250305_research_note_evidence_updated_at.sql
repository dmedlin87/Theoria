ALTER TABLE research_notes
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE research_notes
SET updated_at = COALESCE(created_at, NOW())
WHERE updated_at IS NULL;

ALTER TABLE research_notes
    ALTER COLUMN updated_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET NOT NULL;

ALTER TABLE note_evidence
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE note_evidence
SET updated_at = COALESCE(created_at, NOW())
WHERE updated_at IS NULL;

ALTER TABLE note_evidence
    ALTER COLUMN updated_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET NOT NULL;
