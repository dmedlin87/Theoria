CREATE INDEX IF NOT EXISTS ix_contradiction_seeds_range_primary
    ON contradiction_seeds (start_verse_id, end_verse_id);
CREATE INDEX IF NOT EXISTS ix_contradiction_seeds_range_b
    ON contradiction_seeds (start_verse_id_b, end_verse_id_b);

CREATE INDEX IF NOT EXISTS ix_harmony_seeds_range_primary
    ON harmony_seeds (start_verse_id, end_verse_id);
CREATE INDEX IF NOT EXISTS ix_harmony_seeds_range_b
    ON harmony_seeds (start_verse_id_b, end_verse_id_b);

CREATE INDEX IF NOT EXISTS ix_commentary_excerpt_seeds_range
    ON commentary_excerpt_seeds (start_verse_id, end_verse_id);
