CREATE TABLE IF NOT EXISTS geo_place (
    ancient_id TEXT PRIMARY KEY,
    friendly_id TEXT NOT NULL,
    classification TEXT,
    raw JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS geo_location (
    modern_id TEXT PRIMARY KEY,
    friendly_id TEXT NOT NULL,
    geom_kind TEXT,
    confidence DOUBLE PRECISION,
    names JSONB,
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    raw JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS geo_place_verse (
    ancient_id TEXT NOT NULL REFERENCES geo_place(ancient_id) ON DELETE CASCADE,
    osis_ref TEXT NOT NULL,
    PRIMARY KEY (ancient_id, osis_ref)
);

CREATE INDEX IF NOT EXISTS idx_geo_place_verse_osis ON geo_place_verse (osis_ref);

CREATE TABLE IF NOT EXISTS geo_geometry (
    geometry_id TEXT PRIMARY KEY,
    geom_type TEXT,
    geojson JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS geo_image (
    image_id TEXT NOT NULL,
    owner_kind TEXT NOT NULL CHECK (owner_kind IN ('ancient', 'modern')),
    owner_id TEXT NOT NULL,
    thumb_file TEXT,
    url TEXT,
    license TEXT,
    attribution TEXT,
    PRIMARY KEY (image_id, owner_kind, owner_id, thumb_file)
);
