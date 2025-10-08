ALTER TABLE research_notes
    ADD COLUMN updated_at TIMESTAMPTZ;

UPDATE research_notes
SET updated_at = COALESCE(created_at, NOW());

ALTER TABLE research_notes
    ALTER COLUMN updated_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET NOT NULL;

ALTER TABLE note_evidence
    ADD COLUMN updated_at TIMESTAMPTZ;

UPDATE note_evidence
SET updated_at = COALESCE(created_at, NOW());

ALTER TABLE note_evidence
    ALTER COLUMN updated_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET NOT NULL;
