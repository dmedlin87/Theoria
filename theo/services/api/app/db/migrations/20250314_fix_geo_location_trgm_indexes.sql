--
-- Rebuild indexes concurrently so the geo_location table stays available
-- during the upgrade.
DROP INDEX CONCURRENTLY IF EXISTS idx_geo_location_friendly_id_trgm;

CREATE INDEX CONCURRENTLY idx_geo_location_friendly_id_trgm
    ON geo_location USING GIN (lower(friendly_id) gin_trgm_ops);

DROP INDEX CONCURRENTLY IF EXISTS idx_geo_location_aliases_trgm;

CREATE INDEX CONCURRENTLY idx_geo_location_aliases_trgm
    ON geo_location USING GIN ((lower(coalesce(array_to_string(search_aliases, ' '), ''))) gin_trgm_ops);
