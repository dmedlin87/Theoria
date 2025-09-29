ALTER TABLE contradiction_seeds
    ADD COLUMN IF NOT EXISTS perspective text;

UPDATE contradiction_seeds
SET perspective = COALESCE(perspective, 'skeptical')
WHERE perspective IS NULL;

ALTER TABLE contradiction_seeds
    ALTER COLUMN perspective SET DEFAULT 'skeptical';

CREATE TABLE IF NOT EXISTS harmony_seeds (
    id uuid PRIMARY KEY,
    osis_a text NOT NULL,
    osis_b text NOT NULL,
    summary text,
    source text,
    tags jsonb,
    weight real DEFAULT 1.0,
    perspective text DEFAULT 'apologetic',
    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_harmony_seeds_osis_a ON harmony_seeds (osis_a);
CREATE INDEX IF NOT EXISTS ix_harmony_seeds_osis_b ON harmony_seeds (osis_b);

CREATE TABLE IF NOT EXISTS commentary_excerpts (
    id uuid PRIMARY KEY,
    osis text NOT NULL,
    title text,
    excerpt text NOT NULL,
    source text,
    citation text,
    tradition text,
    perspective text,
    tags jsonb,
    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_commentary_excerpts_osis ON commentary_excerpts (osis);
CREATE INDEX IF NOT EXISTS ix_commentary_excerpts_perspective ON commentary_excerpts (perspective);
