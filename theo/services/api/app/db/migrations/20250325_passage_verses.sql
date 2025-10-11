CREATE TABLE IF NOT EXISTS passage_verses (
    passage_id TEXT NOT NULL REFERENCES passages(id) ON DELETE CASCADE,
    verse_id INTEGER NOT NULL,
    PRIMARY KEY (passage_id, verse_id)
);

CREATE INDEX IF NOT EXISTS ix_passage_verses_verse_id
    ON passage_verses (verse_id);
