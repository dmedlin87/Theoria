-- Enforce unique job scheduling per job type and argument hash.
CREATE UNIQUE INDEX IF NOT EXISTS ingestion_jobs_job_type_args_hash_uniq
    ON ingestion_jobs (job_type, args_hash)
    WHERE args_hash IS NOT NULL;
