ALTER TABLE contradiction_seeds
    ADD COLUMN IF NOT EXISTS perspective text;

UPDATE contradiction_seeds
SET perspective = COALESCE(perspective, 'skeptical');

CREATE TABLE IF NOT EXISTS harmony_seeds (
    id uuid PRIMARY KEY,
    osis_a text NOT NULL,
    osis_b text NOT NULL,
    summary text,
    source text,
    tags jsonb,
    weight real DEFAULT 1.0,
    perspective text,
    created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_harmony_seeds_osis_a ON harmony_seeds (osis_a);
CREATE INDEX IF NOT EXISTS ix_harmony_seeds_osis_b ON harmony_seeds (osis_b);

CREATE TABLE IF NOT EXISTS commentary_seeds (
    id uuid PRIMARY KEY,
    osis text NOT NULL,
    title text,
    excerpt text NOT NULL,
    source text,
    citation text,
    tags jsonb,
    perspective text,
    created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_commentary_seeds_osis ON commentary_seeds (osis);
