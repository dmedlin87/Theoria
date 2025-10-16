CREATE TABLE IF NOT EXISTS contradiction_seeds (
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

CREATE INDEX IF NOT EXISTS ix_contradiction_seeds_osis_a ON contradiction_seeds (osis_a);
CREATE INDEX IF NOT EXISTS ix_contradiction_seeds_osis_b ON contradiction_seeds (osis_b);

CREATE TABLE IF NOT EXISTS geo_places (
    slug text PRIMARY KEY,
    name text NOT NULL,
    lat double precision,
    lng double precision,
    confidence real,
    aliases jsonb,
    sources jsonb,
    updated_at timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE ingestion_jobs
    ADD COLUMN IF NOT EXISTS args_hash text;

CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_args_hash ON ingestion_jobs (args_hash);

ALTER TABLE ingestion_jobs
    ADD COLUMN IF NOT EXISTS scheduled_at timestamptz;
