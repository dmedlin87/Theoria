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
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # tooling (e.g., mypy) and stub packages
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
  This command will evolve to include coverage (`--cov --cov-branch`) once thresholds are enforced.

- **Celery worker tests** (placeholder)
  ```bash
  pytest -q tests/workers
  ```
  A dedicated `celery` marker and live-worker toggle will be added alongside the new fixtures.

- **Frontend unit tests**
  ```bash
  cd theo/services/web
  npm test
  ```
  The migration to Vitest + Testing Library is tracked in the testing roadmap.

- **Playwright E2E**
  ```bash
  cd theo/services/web
  npx playwright test
  ```
  Smoke vs full suites will be tagged (`@smoke`, `@full`) in upcoming work.

Once the Makefile façade is introduced the following convenience commands will be available:
- `make test` – run everything (Python + frontend + E2E as applicable).
- `make test:unit` – Python-only suites.
- `make test:e2e` – Playwright tagged runs (defaults to `@smoke`).
- `make test:changed` – Frontend unit tests filtered to changed files.

## Style & Linting
- Format Python with `black` and organise imports with `ruff check --select I` (see `pyproject.toml`).
- Type-check selective modules with `mypy` via `python -m mypy` (install `requirements-dev.txt` for stub packages such as `types-PyYAML`).
- Frontend formatting uses `prettier` with repo defaults.

## Pull Request Expectations
- Reference relevant sections of the Test Map when adding or updating tests.
- Include coverage outputs when enabling gates.
- Update documentation for any new fixtures, commands, or workflows.

## Getting Help
- Review the architectural context in `docs/BLUEPRINT.md` and `docs/API.md`.
- For ingestion-specific questions, check `docs/OSIS.md` and `docs/Chunking.md`.
- Reach out via the project Slack channel or open a GitHub discussion for design clarifications.
