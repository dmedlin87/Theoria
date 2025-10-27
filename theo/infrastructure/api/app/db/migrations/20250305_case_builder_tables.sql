-- Case Builder foundational tables for ingestion and scoring

DO $$
BEGIN
    CREATE TYPE case_object_type AS ENUM ('passage', 'note', 'claim', 'evidence');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE case_edge_kind AS ENUM (
        'semantic_sim',
        'co_citation',
        'verse_overlap',
        'topic_overlap',
        'contradiction'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE case_insight_type AS ENUM ('convergence', 'collision', 'lead', 'bundle');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE case_user_action_type AS ENUM ('accept', 'snooze', 'discard', 'pin', 'mute');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS case_sources (
    id TEXT PRIMARY KEY,
    document_id TEXT UNIQUE NULL,
    origin TEXT NULL,
    author TEXT NULL,
    year INTEGER NULL,
    url TEXT NULL,
    modality TEXT NULL,
    meta JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_case_sources_document
        FOREIGN KEY (document_id)
        REFERENCES documents (id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_case_sources_document_id
    ON case_sources (document_id);

CREATE TABLE IF NOT EXISTS case_objects (
    id TEXT PRIMARY KEY,
    source_id TEXT NULL,
    document_id TEXT NULL,
    passage_id TEXT NULL,
    object_type case_object_type NOT NULL DEFAULT 'passage',
    title TEXT NULL,
    body TEXT NULL,
    osis_ranges JSONB NULL,
    modality TEXT NULL,
    tags JSONB NULL,
    embedding VECTOR(1024) NULL,
    stability DOUBLE PRECISION NULL,
    meta JSONB NULL,
    published_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_case_objects_source
        FOREIGN KEY (source_id)
        REFERENCES case_sources (id)
        ON DELETE SET NULL,
    CONSTRAINT fk_case_objects_document
        FOREIGN KEY (document_id)
        REFERENCES documents (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_case_objects_passage
        FOREIGN KEY (passage_id)
        REFERENCES passages (id)
        ON DELETE CASCADE,
    CONSTRAINT uq_case_objects_passage_id UNIQUE (passage_id)
);

CREATE INDEX IF NOT EXISTS ix_case_objects_source_id
    ON case_objects (source_id);

CREATE INDEX IF NOT EXISTS ix_case_objects_document_id
    ON case_objects (document_id);

CREATE INDEX IF NOT EXISTS ix_case_objects_created_at
    ON case_objects (created_at);

CREATE TABLE IF NOT EXISTS case_edges (
    id TEXT PRIMARY KEY,
    src_object_id TEXT NOT NULL,
    dst_object_id TEXT NOT NULL,
    kind case_edge_kind NOT NULL,
    weight DOUBLE PRECISION NULL,
    features JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_case_edges_src
        FOREIGN KEY (src_object_id)
        REFERENCES case_objects (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_case_edges_dst
        FOREIGN KEY (dst_object_id)
        REFERENCES case_objects (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_case_edges_src
    ON case_edges (src_object_id);

CREATE INDEX IF NOT EXISTS ix_case_edges_dst
    ON case_edges (dst_object_id);

CREATE TABLE IF NOT EXISTS case_insights (
    id TEXT PRIMARY KEY,
    primary_object_id TEXT NULL,
    insight_type case_insight_type NOT NULL,
    score DOUBLE PRECISION NULL,
    cluster_id TEXT NULL,
    payload JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_case_insights_primary_object
        FOREIGN KEY (primary_object_id)
        REFERENCES case_objects (id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_case_insights_type
    ON case_insights (insight_type);

CREATE INDEX IF NOT EXISTS ix_case_insights_created_at
    ON case_insights (created_at);

CREATE TABLE IF NOT EXISTS case_user_actions (
    id TEXT PRIMARY KEY,
    insight_id TEXT NOT NULL,
    action case_user_action_type NOT NULL,
    confidence DOUBLE PRECISION NULL,
    payload JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_case_user_actions_insight
        FOREIGN KEY (insight_id)
        REFERENCES case_insights (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_case_user_actions_insight
    ON case_user_actions (insight_id);

