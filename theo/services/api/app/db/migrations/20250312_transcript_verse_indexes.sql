CREATE TABLE IF NOT EXISTS transcript_segment_verses (
    id TEXT PRIMARY KEY,
    segment_id TEXT NOT NULL,
    verse_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_transcript_segment_verses_segment
        FOREIGN KEY (segment_id)
        REFERENCES transcript_segments (id)
        ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_transcript_segment_verses_segment_verse
    ON transcript_segment_verses (segment_id, verse_id);

CREATE INDEX IF NOT EXISTS ix_transcript_segment_verses_segment
    ON transcript_segment_verses (segment_id);

CREATE INDEX IF NOT EXISTS ix_transcript_segment_verses_verse
    ON transcript_segment_verses (verse_id);

CREATE TABLE IF NOT EXISTS transcript_quote_verses (
    id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL,
    verse_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_transcript_quote_verses_quote
        FOREIGN KEY (quote_id)
        REFERENCES transcript_quotes (id)
        ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_transcript_quote_verses_quote_verse
    ON transcript_quote_verses (quote_id, verse_id);

CREATE INDEX IF NOT EXISTS ix_transcript_quote_verses_quote
    ON transcript_quote_verses (quote_id);

CREATE INDEX IF NOT EXISTS ix_transcript_quote_verses_verse
    ON transcript_quote_verses (verse_id);
