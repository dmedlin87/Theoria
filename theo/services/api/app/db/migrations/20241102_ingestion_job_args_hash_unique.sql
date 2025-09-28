-- Enforce unique job scheduling per job type and argument hash.
--
-- Before introducing the unique index, clear any stale duplicate rows that
-- would block the index creation. We keep the newest record per
-- (job_type, args_hash) pair and null-out the hash for older entries so they
-- remain queryable without violating the constraint.
WITH duplicate_jobs AS (
    SELECT id
    FROM (
        SELECT
            id,
            ROW_NUMBER() OVER (
                PARTITION BY job_type, args_hash
                ORDER BY updated_at DESC, created_at DESC, id DESC
            ) AS duplicate_rank
        FROM ingestion_jobs
        WHERE args_hash IS NOT NULL
    ) ranked_jobs
    WHERE duplicate_rank > 1
)
UPDATE ingestion_jobs
SET args_hash = NULL
WHERE id IN (SELECT id FROM duplicate_jobs);

CREATE UNIQUE INDEX IF NOT EXISTS ingestion_jobs_job_type_args_hash_uniq
    ON ingestion_jobs (job_type, args_hash)
    WHERE args_hash IS NOT NULL;
