-- Rebuild geo_location trigram indexes to ensure lower() lookups are supported
DROP INDEX IF EXISTS idx_geo_location_friendly_id_trgm;

CREATE INDEX idx_geo_location_friendly_id_trgm
    ON geo_location USING GIN (lower(friendly_id) gin_trgm_ops);

DROP INDEX IF EXISTS idx_geo_location_aliases_trgm;

CREATE INDEX idx_geo_location_aliases_trgm
    ON geo_location USING GIN ((lower(coalesce(array_to_string(search_aliases, ' '), ''))) gin_trgm_ops);
