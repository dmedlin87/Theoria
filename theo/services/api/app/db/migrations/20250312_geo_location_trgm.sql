-- Enable trigram search and indexes for geo locations
CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE geo_location
    ADD COLUMN IF NOT EXISTS search_aliases TEXT[];

UPDATE geo_location AS target
SET search_aliases = (
    SELECT ARRAY(
        SELECT DISTINCT alias
        FROM (
            SELECT
                CASE
                    WHEN jsonb_typeof(element) = 'string' THEN trim(both '"' FROM element::text)
                    WHEN jsonb_typeof(element) = 'object' THEN element->>'name'
                    ELSE NULL
                END AS alias
            FROM jsonb_array_elements(COALESCE(target.names::jsonb, '[]'::jsonb)) AS element
        ) AS raw_aliases
        WHERE alias IS NOT NULL
          AND btrim(alias) <> ''
          AND lower(alias) <> lower(target.friendly_id)
        ORDER BY alias
    )
)
WHERE target.search_aliases IS NULL OR target.search_aliases = '{}';

CREATE INDEX IF NOT EXISTS idx_geo_location_friendly_id_trgm
    ON geo_location USING GIN (friendly_id gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_geo_location_aliases_trgm
    ON geo_location USING GIN ((array_to_string(search_aliases, ' ')) gin_trgm_ops);
