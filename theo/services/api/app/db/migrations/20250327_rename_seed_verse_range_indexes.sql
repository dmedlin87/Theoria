DROP INDEX IF EXISTS ix_contradiction_seeds_range_a;
DROP INDEX IF EXISTS ix_contradiction_seeds_range_b;
DROP INDEX IF EXISTS ix_harmony_seeds_range_a;
DROP INDEX IF EXISTS ix_harmony_seeds_range_b;
DROP INDEX IF EXISTS ix_commentary_excerpt_seeds_range;

CREATE INDEX IF NOT EXISTS ix_contradiction_seeds_range_primary
    ON contradiction_seeds (start_verse_id, end_verse_id);
CREATE INDEX IF NOT EXISTS ix_contradiction_seeds_range_secondary
    ON contradiction_seeds (start_verse_id_b, end_verse_id_b);

CREATE INDEX IF NOT EXISTS ix_harmony_seeds_range_primary
    ON harmony_seeds (start_verse_id, end_verse_id);
CREATE INDEX IF NOT EXISTS ix_harmony_seeds_range_secondary
    ON harmony_seeds (start_verse_id_b, end_verse_id_b);

CREATE INDEX IF NOT EXISTS ix_commentary_excerpt_seeds_range_primary
    ON commentary_excerpt_seeds (start_verse_id, end_verse_id);
