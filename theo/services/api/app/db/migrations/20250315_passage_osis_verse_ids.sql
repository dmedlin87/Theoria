-- Add verse identifier range tracking to passages for efficient OSIS lookups
ALTER TABLE passages ADD COLUMN osis_start_verse_id INTEGER;
ALTER TABLE passages ADD COLUMN osis_end_verse_id INTEGER;

CREATE INDEX IF NOT EXISTS ix_passages_osis_start_verse_id
    ON passages (osis_start_verse_id);
CREATE INDEX IF NOT EXISTS ix_passages_osis_end_verse_id
    ON passages (osis_end_verse_id);
