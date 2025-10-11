-- Add search_terms column and trigram index for geo_location similarity lookups
CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE geo_location
    ADD COLUMN IF NOT EXISTS search_terms TEXT;

UPDATE geo_location
SET search_terms = lower(trim(friendly_id))
WHERE friendly_id IS NOT NULL;

UPDATE geo_location AS gl
SET search_terms = lower(trim(concat_ws(' ', gl.search_terms, alias_data.aliases)))
FROM (
    SELECT modern_id,
           string_agg(alias, ' ') AS aliases
    FROM (
        SELECT DISTINCT
            gl.modern_id,
            CASE jsonb_typeof(elem)
                WHEN 'object' THEN NULLIF(btrim(elem->>'name'), '')
                WHEN 'string' THEN NULLIF(trim(both '"' from elem::text), '')
                ELSE NULL
            END AS alias
        FROM geo_location AS gl
        CROSS JOIN LATERAL jsonb_array_elements(COALESCE(gl.names, '[]'::jsonb)) AS elem
    ) AS raw
    WHERE alias IS NOT NULL
    GROUP BY modern_id
) AS alias_data
WHERE alias_data.modern_id = gl.modern_id;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_geo_location_search_terms_trgm
    ON geo_location USING gin (search_terms gin_trgm_ops);
