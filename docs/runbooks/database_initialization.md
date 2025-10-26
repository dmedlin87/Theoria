# Database Initialization Runbook

This runbook describes how to bring a Theo database up to date with the
performance-sensitive indexes required by the ingestion and retrieval
pipelines. The key indexes introduced by this change are:

- `idx_passages_embedding_null` – speeds up polling for passages that still
  need embeddings.
- `idx_documents_updated_at` – supports ordering document refresh jobs by the
  latest update timestamp.
- `idx_passages_document_id` – accelerates joins between documents and their
  passages.

## Alembic-managed deployments

1. Install Alembic if it is not already available: `pip install alembic`.
2. Export `DATABASE_URL` for the target environment (for example
   `postgresql+psycopg://user:pass@host:5432/theo`).
3. Run the migration suite:

   ```bash
   alembic -c theo/adapters/persistence/migrations/alembic.ini upgrade head
   ```

   The migration creates the indexes using PostgreSQL's `CONCURRENTLY` option
   so production traffic can continue while they are built.

## Environments without Alembic

Legacy and lightweight environments (such as SQLite-backed tests) should run
the existing SQL migration runner, which now enforces the same indexes:

```bash
python -m theo.services.api.app.db.run_sql_migrations
```

The runner detects the database dialect and applies either PostgreSQL
(`CREATE INDEX CONCURRENTLY ...`) or SQLite-compatible statements, creating
only the indexes that are missing.

## Verification checklist

After running either workflow, verify that the indexes exist:

- **PostgreSQL:**

  ```bash
  psql $DATABASE_URL -c "\di+ idx_passages_embedding_null idx_documents_updated_at idx_passages_document_id"
  ```

- **SQLite:**

  ```bash
  sqlite3 path/to/theo.db \
    "PRAGMA index_list('passages');" \
    "PRAGMA index_list('documents');"
  ```

Record the index creation in your deployment notes along with the command
output for future troubleshooting.
