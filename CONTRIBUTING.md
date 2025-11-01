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
   pip install ".[api]" -c constraints/prod.txt
   pip install ".[ml]" -c constraints/prod.txt
   pip install ".[dev]" -c constraints/dev.txt  # tooling (e.g., mypy) and stub packages

After editing dependency ranges in `pyproject.toml`, regenerate the constraint lockfiles via `python scripts/update_constraints.py` and commit the results. Use `python scripts/update_constraints.py --check` locally or in CI to ensure constraints stay in sync.
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
  pytest -q theo/infrastructure/api/tests/workers
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

### Postgres + pgvector Testcontainer fixture

The shared pgvector integration fixture lives in [`tests/conftest.py`](tests/conftest.py). It starts a disposable Postgres instance with `pgvector` and `pg_trgm` enabled via [`testcontainers`](https://github.com/testcontainers/testcontainers-python). Opt in explicitly to run the suite locally:

```bash
pytest --pgvector -m pgvector
```

Keep the following workflow in mind:

- Ensure Docker Engine is available (`docker info`) and install the supporting extras: `pip install "testcontainers[postgresql]"` plus the repository’s `.[api]` extra.
- Override the container image when necessary with `PYTEST_PGVECTOR_IMAGE=<registry/image:tag>`.
- `--pgvector` implies `--schema`, so Alembic migrations run once before the tests execute. Use `--schema` by itself for SQLite-backed migrations.
- Legacy shims (`--use-pgvector` and `PYTEST_USE_PGVECTOR=1`) still work, but new suites should rely on the explicit flag and decorate tests with `@pytest.mark.pgvector`. The collection hook raises a `pytest.UsageError` if a pgvector fixture is consumed without the marker.

### Targeted pytest execution

- Focus the run on a directory or module: `pytest tests/api/test_rag_guardrails.py` or `pytest tests/api -k "watchlist"`.
- Filter by marker: `pytest -m "pgvector and not slow"` or `pytest --schema -m contract`.
- Exercise the slow suites against Postgres: `pytest --schema --pgvector -m slow`.
- Let the wrapper script discover optional plugins automatically: `python run_tests.py` adds timeouts, xdist parallelism, and coverage flags whenever the plugins are installed.
- Profiling helpers such as `python scripts/perf/profile_marker_suites.py` capture baseline timings for heavy suites before you land optimisations.

### Targeted Vitest, Playwright, and MCP runs

- Run a single component test: `npm run test:vitest -- --run tests/app/onboarding/onboarding-wizard.test.tsx`.
- Filter by test name: `npm run test:vitest -- --testNamePattern="Wizard completes"`.
- To run Vitest tests without collecting coverage, use: `npm run test:vitest -- --coverage=false`.
- Trigger Playwright against a tag or specific spec: `npm run test:e2e -- --grep @smoke` or `npm run test:e2e -- tests/e2e/chat.spec.ts`.
- Regenerate the MCP contract fixtures after API changes with `task test:contract`.

### Coverage artefacts and dashboards

- **Python (pytest-cov)** – `python -m pytest --cov=theo --cov=mcp_server --cov-report=xml --cov-report=html` writes `coverage.xml` plus an `htmlcov/` dashboard. Summarise or compare runs with `python analyze_coverage.py`.
- **JSON comparisons** – Produce machine-readable diffs with `coverage json -o coverage.json` and inspect deltas via `jq` or downstream tooling; regenerate `coverage.xml` afterwards so `python analyze_coverage.py` can summarise the run.
- **Frontend (Vitest)** – `npm run test:vitest` emits V8 coverage in `theo/services/web/coverage/`; open `theo/services/web/coverage/index.html` to review the per-file breakdown.
- **Playwright** – Every E2E run writes `playwright-report/` with HTML, HAR, and trace archives. Add `--trace on` during investigations so GitHub Actions uploads the bundle automatically.
- **Dashboards** – [`dashboard/coverage-dashboard.md`](dashboard/coverage-dashboard.md) lists the canonical commands and report locations for each stack.

## Optional dependencies & troubleshooting

- Run `python validate_test_env.py` (or `task test:validate-env`) when pytest cannot discover plugins such as `pytest-xdist` or `pytest-timeout`. The script lists missing requirements and suggests `pip install -e '.[dev]'`.
- Heavy fixtures are opt-in via CLI flags: `--schema` (migrations), `--pgvector` (Testcontainer Postgres), `--contract` (Schemathesis), and `--gpu` (ML extras). Combine them explicitly so your local environment matches CI.
- If you see messages about placeholder SQLAlchemy modules, install the database extras (`pip install 'sqlalchemy[asyncio]' psycopg[binary]`) so pytest can import the real engine instead of the lightweight stubs bundled under `tests/conftest.py`.
- Enable the regression factories by keeping the bundled `faker/` module on `PYTHONPATH`; reinstall the editable package (`pip install -e .[dev]`) if imports fail.
- When `testcontainers` cannot pull images because of a corporate registry mirror, pre-pull the image (`docker pull ankane/pgvector:0.5.2`) or point to an approved mirror with `PYTEST_PGVECTOR_IMAGE`.
- GPU-heavy suites expect the `.[ml]` extra; install it alongside CUDA/Torch if you plan to exercise the `@pytest.mark.gpu` tests or the ranking CLI slow path.

## Style & Linting
- Format Python with `black` and organise imports with `ruff check --select I` (see `pyproject.toml`).
- Type-check selective modules with `mypy` via `python -m mypy` (install the `[dev]` extra for stub packages such as `types-PyYAML`).
- Frontend formatting uses `prettier` with repo defaults.

## Debugging Utilities & Local Artifacts
- Reusable maintenance helpers and scratch scripts live in [`scripts/debug/`](scripts/debug/). If you create a new diagnostic script, place it there so others can discover and rerun it.
- Store ad-hoc transcripts or large local investigation logs under `docs/process/` when they are worth sharing, or `.debug/` when they should stay out of version control. Avoid committing machine-specific transcripts, temporary exports (for example `test_results*.txt`), or other local debugging output at the repository root.
- Do not recreate the legacy `.tmp_contract_debug/` workspace (or similarly named folders). It was an ad-hoc scratch area that polluted commits; use `.debug/` or `docs/process/` instead so temporary assets stay local.

## Pull Request Expectations
- Reference relevant sections of the Test Map when adding or updating tests.
- Include coverage outputs when enabling gates.
- Update documentation for any new fixtures, commands, or workflows.

## Getting Help
- Review the architectural context in `docs/BLUEPRINT.md` and `docs/API.md`.
- For ingestion-specific questions, check `docs/OSIS.md` and `docs/Chunking.md`.
- Reach out via the project Slack channel or open a GitHub discussion for design clarifications.
