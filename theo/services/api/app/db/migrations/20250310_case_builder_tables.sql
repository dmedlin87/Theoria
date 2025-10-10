-- Case Builder foundation: sources, objects, edges, insights, and user actions

CREATE TABLE IF NOT EXISTS case_sources (
    id TEXT PRIMARY KEY,
    document_id TEXT UNIQUE REFERENCES documents(id) ON DELETE SET NULL,
    origin TEXT NULL,
    author TEXT NULL,
    year INTEGER NULL,
    url TEXT NULL,
    modality TEXT NULL,
    meta JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS case_objects (
    id TEXT PRIMARY KEY,
    source_id TEXT NULL REFERENCES case_sources(id) ON DELETE SET NULL,
    document_id TEXT NULL REFERENCES documents(id) ON DELETE SET NULL,
    passage_id TEXT UNIQUE NULL REFERENCES passages(id) ON DELETE SET NULL,
    annotation_id TEXT UNIQUE NULL REFERENCES document_annotations(id) ON DELETE SET NULL,
    object_type TEXT NOT NULL,
    title TEXT NULL,
    body TEXT NOT NULL,
    osis_ranges JSONB NULL,
    modality TEXT NULL,
    tags JSONB NULL,
    stability DOUBLE PRECISION NULL,
    embedding VECTOR(1024) NULL,
    published_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    meta JSONB NULL
);

CREATE INDEX IF NOT EXISTS ix_case_objects_document_id
    ON case_objects (document_id);
CREATE INDEX IF NOT EXISTS ix_case_objects_object_type
    ON case_objects (object_type);
CREATE INDEX IF NOT EXISTS ix_case_objects_created_at
    ON case_objects (created_at);
CREATE INDEX IF NOT EXISTS ix_case_objects_embedding
    ON case_objects USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS case_edges (
    id TEXT PRIMARY KEY,
    src_object_id TEXT NOT NULL REFERENCES case_objects(id) ON DELETE CASCADE,
    dst_object_id TEXT NOT NULL REFERENCES case_objects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    weight DOUBLE PRECISION NULL,
    features JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_case_edges_src
    ON case_edges (src_object_id);
CREATE INDEX IF NOT EXISTS ix_case_edges_dst
    ON case_edges (dst_object_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_case_edges_pair_kind
    ON case_edges (src_object_id, dst_object_id, kind);

CREATE TABLE IF NOT EXISTS case_insights (
    id TEXT PRIMARY KEY,
    insight_type TEXT NOT NULL,
    primary_object_id TEXT NULL REFERENCES case_objects(id) ON DELETE SET NULL,
    score DOUBLE PRECISION NULL,
    payload JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_case_insights_type
    ON case_insights (insight_type);
CREATE INDEX IF NOT EXISTS ix_case_insights_created_at
    ON case_insights (created_at);

CREATE TABLE IF NOT EXISTS case_user_actions (
    id TEXT PRIMARY KEY,
    insight_id TEXT NOT NULL REFERENCES case_insights(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    confidence DOUBLE PRECISION NULL,
    meta JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_case_user_actions_insight
    ON case_user_actions (insight_id);
CREATE INDEX IF NOT EXISTS ix_case_user_actions_action
    ON case_user_actions (action);
