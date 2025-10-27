-- Improve watchlist analytics performance by indexing timestamp lookups.
--
-- The watchlist collection jobs filter Documents by created_at and
-- paginate WatchlistEvent rows ordered by run_started. Indexing these
-- columns keeps the planner on index scans instead of table scans for
-- large datasets.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_documents_created_at
    ON documents (created_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_watchlist_events_watchlist_id_run_started
    ON watchlist_events (watchlist_id, run_started);
