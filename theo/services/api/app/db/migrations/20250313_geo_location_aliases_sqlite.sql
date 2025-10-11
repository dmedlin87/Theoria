-- Ensure geo_location exposes search_aliases on SQLite deployments
ALTER TABLE geo_location ADD COLUMN IF NOT EXISTS search_aliases JSON;
