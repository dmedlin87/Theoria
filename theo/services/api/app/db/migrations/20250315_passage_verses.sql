-- Map passages to normalized verse identifiers

CREATE TABLE IF NOT EXISTS passage_verses (
    id TEXT PRIMARY KEY,
    passage_id TEXT NOT NULL REFERENCES passages(id) ON DELETE CASCADE,
    verse_id INTEGER NOT NULL,
    CONSTRAINT uq_passage_verses_passage_verse UNIQUE (passage_id, verse_id)
);

CREATE INDEX IF NOT EXISTS ix_passage_verses_passage_id
    ON passage_verses (passage_id);

CREATE INDEX IF NOT EXISTS ix_passage_verses_verse_id
    ON passage_verses (verse_id);
