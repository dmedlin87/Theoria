-- Migration: convert embeddings to pgvector and lexeme to tsvector
-- Requires pgvector extension (see infra/db-init/pgvector.sql)

ALTER TABLE passages
    ALTER COLUMN embedding TYPE vector(1024) USING embedding::vector(1024);

ALTER TABLE passages
    ALTER COLUMN lexeme TYPE tsvector USING to_tsvector('english', COALESCE(text, ''));

CREATE INDEX IF NOT EXISTS ix_passages_embedding_hnsw
    ON passages USING hnsw (embedding vector_l2_ops);

CREATE INDEX IF NOT EXISTS ix_passages_lexeme
    ON passages USING gin (lexeme);
