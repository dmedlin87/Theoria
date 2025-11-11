> **Archived on 2025-10-26**

# Next PR Proposal: Restore Contradiction Seed Perspective Column

## Context
- API startup seeds contradiction data by reading bundled JSON/YAML payloads and persisting them via the `ContradictionSeed` ORM model, which expects a `perspective` column to exist on the `contradiction_seeds` table.【F:theo/infrastructure/api/app/db/seeds.py†L63-L116】【F:theo/infrastructure/api/app/db/models.py†L613-L636】
- Recent test runs crash during application startup because SQLite raises `OperationalError: no such column: contradiction_seeds.perspective` when the seeder tries to hydrate existing rows without that column. The failure happens before any of the AI export or ingestion tests can execute.【F:test_results.txt†L1-L120】
- In the test harness we currently monkeypatch `run_sql_migrations` to a no-op, so the migration that adds the new column (`20250129_add_perspective_to_contradiction_seeds.sql`) never executes against pre-existing databases that were created before the column existed.【F:tests/api/conftest.py†L33-L51】【F:theo/infrastructure/api/app/db/migrations/20250129_add_perspective_to_contradiction_seeds.sql†L1-L4】

## Proposed changes
1. **Ensure migrations run for API tests when schema drift matters.** Update the `_disable_migrations` fixture (or add a new helper) so that it still applies idempotent migrations needed for SQLite test databases while keeping the fast path for tests that explicitly opt out. This guarantees the contradiction perspective column is created before seeding while preserving the existing override hooks for exceptional cases.
2. **Backfill the column for in-memory databases.** Add a lightweight guard in `seed_contradiction_claims` that inspects the available columns and skips the perspective update when the column truly does not exist. This protects local developer smoke tests or bespoke fixtures that may still bypass migrations entirely.
3. **Add regression coverage.** Extend `tests/db/test_sqlite_migrations.py` (or add an API-level smoke test) to assert that the contradiction seeds can be loaded without raising when migrations are skipped, ensuring future schema additions include either a migration or a defensive fallback.

## Expected impact
- Restores the full API test suite by allowing the seeding process to complete successfully.
- Reduces the risk of future migration-related regressions by covering the interaction between raw SQL migrations and SQLite fixtures.
- Keeps runtime overhead low by only executing the necessary migration logic during tests that exercise application startup.
