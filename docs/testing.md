# Testing prerequisites

This guide summarises the external services, optional dependencies, and environment variables required when running the slower
regression-focused portions of the Python test suite.

## Regression suites

### Commentary ingestion

* **Scope** – `tests/ingest/test_osis_import.py` exercises the full OSIS commentary pipeline including fixture-backed sample
  documents and database preparation helpers. 【F:tests/ingest/test_osis_import.py†L1-L142】
* **Recommended command** – `pytest tests/ingest/test_osis_import.py`
* **Why it exists** – replaces the ad-hoc `temp_*.py` scratch scripts that previously lived in the repository root and ensures
  commentary ingestion is validated through real tests rather than manual helpers.

### Guardrail and RAG regressions

* **Scope** – `tests/api/test_rag_guardrails.py`, `tests/api/test_rag_prompts.py`, and the job enqueue regression under
  `tests/api/test_jobs_enqueue_regression.py` keep golden guardrail metadata, prompt rendering, and Celery hand-offs stable.
* **Data dependencies** – These tests rely on the shared `regression_factory` fixture which synthesises deterministic passages
  via `pythonbible` and the bundled Faker stub. No external datasets are required as long as the repository's `faker/`
  module remains on the `PYTHONPATH`. 【F:tests/fixtures/regression_factory.py†L12-L114】【F:tests/conftest.py†L166-L177】
* **Background workers** – Celery is forced into eager mode during tests, so no broker or worker process needs to be started
  before running the suite. 【F:tests/conftest.py†L229-L263】
* **Suggested command** – `pytest tests/api/test_rag_guardrails.py tests/api/test_rag_prompts.py tests/api/test_jobs_enqueue_regression.py`
  (already part of the default fast loop).

### Red-team regression harness

* **Scope** – `tests/redteam/test_ai_redteam.py` exercises refusal and citation guardrails across chat, verse, and sermon
  workflows using the `RedTeamHarness`. 【F:tests/redteam/test_ai_redteam.py†L1-L119】
* **Database** – The harness seeds a lightweight SQLite schema on demand; no Postgres container is required. 【F:tests/redteam/harness.py†L19-L62】
* **Environment** – API defaults (`SETTINGS_SECRET_KEY`, `THEO_API_KEYS`, `THEO_ALLOW_INSECURE_STARTUP`,
  `THEO_FORCE_EMBEDDING_FALLBACK`) are injected by `tests/api/conftest.py`, so only custom local overrides need to set them
  manually. 【F:tests/api/conftest.py†L1-L33】
* **Suggested command** – `pytest tests/redteam/test_ai_redteam.py`

### Watchlist performance regressions

* **Scope** – `tests/api/test_watchlist_performance.py` verifies index usage for watchlist queries.
* **Database** – Tests use transient SQLite files; migrations are applied directly and no external service is required.
  【F:tests/api/test_watchlist_performance.py†L1-L54】

## Slow-path suites

### Contradiction engine (transformer-backed)

* **Scope** – `tests/domain/discoveries/test_contradiction_engine.py` loads the MNLI transformer to validate contradiction
  detection end-to-end. 【F:tests/domain/discoveries/test_contradiction_engine.py†L174-L229】
* **Dependencies** – Requires `transformers` and `torch` to be installed and downloads ~400 MB for the first run. Plan for
  GPU-less execution unless CUDA wheels are available. Install via `pip install "transformers[torch]"` before invoking
  `pytest -m slow -k contradiction_engine`.

### Full repository round-trip

* **Scope** – `TestRepositoryIntegration::test_full_stack_list_discoveries` inside
  `tests/api/routes/test_discoveries_v1.py` verifies the SQLAlchemy repository against a migrated database. 【F:tests/api/routes/test_discoveries_v1.py†L204-L248】
* **Database** – Runs on the session-scoped SQLite template provided by `tests/api/conftest.py`; pass `--schema` to allow
  migrations to run. No Docker container is required for this slow test.

### Ranking CLI slow path

* **Scope** – `tests/ranking/test_reranker_scripts.py` shells out to `scripts/train_reranker.py` and `scripts/eval_reranker.py`
  to ensure the CLI tooling trains and reports metrics end-to-end. 【F:tests/ranking/test_reranker_scripts.py†L1-L52】
* **Dependencies** – Installs succeed without scikit-learn thanks to bundled stubs, but installing the ML extra unlocks
  histogram gradient boosting (`pip install ".[ml]" -c constraints/prod.txt`).

## Database-backed integration fixtures

Some regression tests opt into database fixtures that can target either SQLite or Postgres + pgvector.

* Passing `--schema` allows schema migrations and enables fixtures such as `integration_database_url`.
* Passing `--pgvector` (or the deprecated `--use-pgvector`) starts a Postgres Testcontainer via `testcontainers`, so Docker
  must be running locally and the `testcontainers[postgresql]` dependency installed. Override the base image with
  `PYTEST_PGVECTOR_IMAGE` when necessary. 【F:tests/conftest.py†L103-L465】
* The fixture ensures the `vector` and `pg_trgm` extensions are present before yielding the connection string. 【F:tests/conftest.py†L423-L430】
* See `docs/testing/pytest_performance.md` for guidance on profiling the heavy marker suites and reviewing baseline timings.

To run the schema-aware slow suite against Postgres:

```bash
pytest --schema --pgvector -m "slow"
```

Ensure Docker is available first, for example:

```bash
docker info  # verifies the daemon is reachable
```

## Environment variables

The following defaults are applied automatically when running tests, but must be exported manually when invoking components
outside pytest:

| Variable | Default | Source |
| --- | --- | --- |
| `THEO_ALLOW_INSECURE_STARTUP` | `1` | `tests/conftest.py`【F:tests/conftest.py†L225-L263】 |
| `THEORIA_ENVIRONMENT` | `development` | `tests/conftest.py`【F:tests/conftest.py†L225-L263】 |
| `THEORIA_TESTING` | `1` | `tests/conftest.py`【F:tests/conftest.py†L229-L263】 |
| `SETTINGS_SECRET_KEY` | `test-secret-key` | `tests/api/conftest.py`【F:tests/api/conftest.py†L1-L33】 |
| `THEO_API_KEYS` | `["pytest-default-key"]` | `tests/api/conftest.py`【F:tests/api/conftest.py†L1-L33】 |
| `THEO_FORCE_EMBEDDING_FALLBACK` | `1` | `tests/api/conftest.py`【F:tests/api/conftest.py†L1-L33】 |

Export these values (or suitable overrides) before running CLI tools or manual smoke tests that depend on the same assumptions.

## Quick reference

| Suite | Command |
| --- | --- |
| Guardrail regressions | `pytest tests/api/test_rag_guardrails.py tests/api/test_rag_prompts.py tests/api/test_jobs_enqueue_regression.py` |
| Red-team regressions | `pytest tests/redteam/test_ai_redteam.py` |
| Watchlist performance | `pytest tests/api/test_watchlist_performance.py` |
| Slow transformers | `pip install "transformers[torch]" && pytest -m slow -k contradiction_engine` |
| Ranking CLI slow path | `pip install ".[ml]" -c constraints/prod.txt && pytest -m slow -k reranker_scripts` |
| Postgres-backed slow suite | `docker info && pytest --schema --pgvector -m "slow"` |
