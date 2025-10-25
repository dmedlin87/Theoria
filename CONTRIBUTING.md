# Contributing to Theoria

Thank you for investing time into Theoria! This guide captures the current development workflow and the near-term testing plan captured in [`docs/testing/TEST_MAP.md`](docs/testing/TEST_MAP.md).

## Prerequisites
- Python 3.11 with `pipx` or virtualenv management.
- Node.js 20 LTS + pnpm or npm (the web app currently uses `npm` scripts).
- Docker Desktop or a compatible runtime for local Postgres / pgvector containers.
- Redis (for Celery broker/backend) – a container definition will be supplied alongside the upcoming test harness.

## Environment Setup
1. Clone the repository and create a Python virtual environment:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install ".[api]" -c constraints/api.txt
   pip install ".[ml]" -c constraints/ml.txt
   pip install ".[dev]" -c constraints/dev.txt  # tooling (e.g., mypy) and stub packages
   ```
2. Install web dependencies:
   ```bash
   cd theo/services/web
   npm install
   ```
3. (Optional) Install Playwright browsers for end-to-end tests:
   ```bash
   npx playwright install --with-deps
   ```

## Running Tests
Testing is being standardised in phases. Until the unified Make targets land, you can run the suites directly:

- **Python unit/integration tests**
  ```bash
  pytest -q
  ```
  To exercise the pgvector-backed flows locally, add `--use-pgvector` (or set `PYTEST_USE_PGVECTOR=1`) so the shared Testcontainer fixtures bootstrap Postgres + pgvector and apply migrations once per session.

- **Scripture heuristics property tests**
  ```bash
  pytest tests/ingest/test_osis_property.py
  ```
  The Hypothesis suite stress-tests OSIS range parsing and chunking heuristics with generated data. When a failure is found the reproducible seed is printed so you can recreate the scenario locally.

- **Celery worker retry/idempotency tests**
  ```bash
  pytest -q theo/services/api/tests/workers
  ```
  Tests in `tests/workers/test_tasks.py` use `celery.contrib.pytest` to validate retry backoff windows and ingestion job idempotency. Pass `--use-pgvector` if you need a Postgres + pgvector backend instead of the default in-memory SQLite database.

- **Frontend unit tests**
  ```bash
  cd theo/services/web
  npm test          # legacy Jest assertions
  npm run test:vitest  # Vitest + coverage thresholds
  ```
  Vitest aggregates V8 coverage and enforces the configured thresholds; Jest remains for backwards compatibility during the migration window.

- **Playwright E2E**
  ```bash
  cd theo/services/web
  npm run test:e2e:smoke  # tagged fast journeys (CI default)
  npm run test:e2e:full   # full regression matrix with traces
  ```
  Smoke journeys run tests tagged with `@smoke`; full journeys focus on flows tagged `@full`. Each journey attaches synthetic artifacts (JSON payloads, screenshots, trace archives) which are persisted in CI for post-failure triage.

Once the Makefile façade is introduced the following convenience commands will be available:
- `make test` – run everything (Python + frontend + E2E as applicable).
- `make test:unit` – Python-only suites.
- `make test:e2e` – Playwright tagged runs (defaults to `@smoke`).
- `make test:changed` – Frontend unit tests filtered to changed files.

## Style & Linting
- Format Python with `black` and organise imports with `ruff check --select I` (see `pyproject.toml`).
- Type-check selective modules with `mypy` via `python -m mypy` (install the `[dev]` extra for stub packages such as `types-PyYAML`).
- Frontend formatting uses `prettier` with repo defaults.

## Debugging Utilities & Local Artifacts
- Reusable maintenance helpers and scratch scripts live in [`scripts/debug/`](scripts/debug/). If you create a new diagnostic script, place it there so others can discover and rerun it.
- Store ad-hoc transcripts or large local investigation logs under `docs/process/` when they are worth sharing, or `.debug/` when they should stay out of version control. Avoid committing machine-specific transcripts, temporary exports (for example `test_results*.txt`), or other local debugging output at the repository root.

## Pull Request Expectations
- Reference relevant sections of the Test Map when adding or updating tests.
- Include coverage outputs when enabling gates.
- Update documentation for any new fixtures, commands, or workflows.

## Getting Help
- Review the architectural context in `docs/architecture/clean-architecture.md` and `docs/development/api-reference.md`.
- For ingestion-specific questions, check `docs/development/osis.md` and `docs/development/chunking.md`.
- Reach out via the project Slack channel or open a GitHub discussion for design clarifications.
