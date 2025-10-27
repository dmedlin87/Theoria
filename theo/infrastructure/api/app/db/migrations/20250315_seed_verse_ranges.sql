ALTER TABLE contradiction_seeds
    ADD COLUMN start_verse_id INTEGER;
ALTER TABLE contradiction_seeds
    ADD COLUMN end_verse_id INTEGER;
ALTER TABLE contradiction_seeds
    ADD COLUMN start_verse_id_b INTEGER;
ALTER TABLE contradiction_seeds
    ADD COLUMN end_verse_id_b INTEGER;

CREATE INDEX IF NOT EXISTS ix_contradiction_seeds_start_verse_id
    ON contradiction_seeds (start_verse_id);
CREATE INDEX IF NOT EXISTS ix_contradiction_seeds_end_verse_id
    ON contradiction_seeds (end_verse_id);
CREATE INDEX IF NOT EXISTS ix_contradiction_seeds_start_verse_id_b
    ON contradiction_seeds (start_verse_id_b);
CREATE INDEX IF NOT EXISTS ix_contradiction_seeds_end_verse_id_b
    ON contradiction_seeds (end_verse_id_b);

ALTER TABLE harmony_seeds
    ADD COLUMN start_verse_id INTEGER;
ALTER TABLE harmony_seeds
    ADD COLUMN end_verse_id INTEGER;
ALTER TABLE harmony_seeds
    ADD COLUMN start_verse_id_b INTEGER;
ALTER TABLE harmony_seeds
    ADD COLUMN end_verse_id_b INTEGER;

CREATE INDEX IF NOT EXISTS ix_harmony_seeds_start_verse_id
    ON harmony_seeds (start_verse_id);
CREATE INDEX IF NOT EXISTS ix_harmony_seeds_end_verse_id
    ON harmony_seeds (end_verse_id);
CREATE INDEX IF NOT EXISTS ix_harmony_seeds_start_verse_id_b
    ON harmony_seeds (start_verse_id_b);
CREATE INDEX IF NOT EXISTS ix_harmony_seeds_end_verse_id_b
    ON harmony_seeds (end_verse_id_b);

ALTER TABLE commentary_excerpt_seeds
    ADD COLUMN start_verse_id INTEGER;
ALTER TABLE commentary_excerpt_seeds
    ADD COLUMN end_verse_id INTEGER;

CREATE INDEX IF NOT EXISTS ix_commentary_excerpt_seeds_start_verse_id
    ON commentary_excerpt_seeds (start_verse_id);
CREATE INDEX IF NOT EXISTS ix_commentary_excerpt_seeds_end_verse_id
    ON commentary_excerpt_seeds (end_verse_id);
