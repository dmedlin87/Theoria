CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'geo_location'
          AND column_name = 'search_terms'
    ) THEN
        ALTER TABLE geo_location
            ADD COLUMN search_terms TEXT[];
    ELSE
        PERFORM 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'geo_location'
          AND column_name = 'search_terms'
          AND data_type = 'ARRAY';

        IF NOT FOUND THEN
            ALTER TABLE geo_location
                ALTER COLUMN search_terms TYPE TEXT[]
                USING CASE
                    WHEN search_terms IS NULL THEN NULL
                    ELSE string_to_array(search_terms, ' ')
                END;
        END IF;
    END IF;
END $$;

UPDATE geo_location
SET search_terms = ARRAY[lower(trim(friendly_id))]
WHERE friendly_id IS NOT NULL;

WITH alias_data AS (
    SELECT modern_id,
           ARRAY_AGG(alias) FILTER (WHERE alias IS NOT NULL) AS aliases
    FROM (
        SELECT DISTINCT
            gl.modern_id,
            CASE jsonb_typeof(elem)
                WHEN 'object' THEN NULLIF(lower(trim(elem->>'name')), '')
                WHEN 'string' THEN NULLIF(lower(trim(both '"' FROM elem::text)), '')
                ELSE NULL
            END AS alias
        FROM geo_location AS gl
        CROSS JOIN LATERAL jsonb_array_elements(COALESCE(gl.names, '[]'::jsonb)) AS elem
    ) AS extracted
    GROUP BY modern_id
)
UPDATE geo_location AS gl
SET search_terms = (
    SELECT ARRAY(
        SELECT DISTINCT term
        FROM unnest(
            COALESCE(gl.search_terms, ARRAY[]::TEXT[])
            || COALESCE(alias_data.aliases, ARRAY[]::TEXT[])
        ) AS term
        WHERE term IS NOT NULL AND length(trim(term)) > 0
    )
)
FROM alias_data
WHERE alias_data.modern_id = gl.modern_id;

DROP INDEX IF EXISTS idx_geo_location_search_terms_trgm;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_geo_location_friendly_id_trgm
    ON geo_location USING gin (friendly_id gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_geo_location_search_terms_trgm
    ON geo_location USING gin (search_terms gin_trgm_ops);
