# Test Suite Issues and Inefficiencies

## Database seeding and migration coupling
- Multiple API tests spin up the FastAPI `TestClient` without requesting the `api_engine` fixture, so the application reuses whatever persistent database `DATABASE_URL` points to. When that database predates the `perspective` column, startup fails while seeding reference data, preventing the tests from running at all.【F:tests/api/test_ai_exports.py†L55-L112】【F:test_results.txt†L2400-L2444】
- Even in modules that *do* depend on `api_engine`, the session-scope fixtures only stub migrations by default and leave `seed_reference_data` enabled; if the template database is out of date, the seeding step issues live queries and crashes before the overrides take effect.【F:tests/api/conftest.py†L48-L140】【F:theo/services/api/app/main.py†L131-L158】【F:theo/services/api/app/db/seeds.py†L324-L399】【F:test_results.txt†L2400-L2423】
  - Because `seed_reference_data` probes for the `perspective` column by reading rows (via `Session.get`), a legacy SQLite file yields `sqlite3.OperationalError: no such column: contradiction_seeds.perspective`, halting every API-level test suite early.【F:theo/services/api/app/db/seeds.py†L760-L839】【F:test_results.txt†L2408-L2426】
- **Impact:** Any developer with an older SQLite snapshot or a fresh checkout without migrations applied cannot run the API tests; the failure happens before a single assertion executes.
- **Suggested actions:** Ensure API tests always opt into `api_engine` (or a similar isolated, migrated database), make the `seed_reference_data` autouse override active, and add a smoke test that asserts the `perspective` column exists so the failure is explicit and actionable instead of a cascading OperationalError.

## URL ingestion error handling regression in tests
- The URL ingestion tests stub `run_pipeline_for_url` to assert that timeouts, oversized responses, and redirect loops raise `UnsupportedSourceError` with human-friendly messages.【F:tests/api/test_ingest.py†L557-L698】
- In practice the API now returns HTTP 500 for these scenarios, indicating that the stubbed pipeline raises an unexpected exception (likely an uncaught assertion) and the route propagates an internal error.【F:test_results.txt†L2625-L2654】
- **Impact:** These regressions mask real regressions in the ingest error path and prevent the tests from validating customer-facing responses.
- **Suggested actions:** Reconcile the helpers with the current pipeline contract—either adapt `_install_url_pipeline_stub` to mimic the latest fetch pipeline behavior or adjust the expectations to the new API responses.

## Ledger deduplication test mismatches runtime behavior
- `test_router_deduplicates_inflight_requests` expects that marking an inflight row as an error still produces a shared cached response once the first request completes.【F:tests/api/test_ai_router.py†L434-L520】
- The shared ledger now raises `GenerationError("Deduplicated generation completed without a result")` when a waiter observes an error row without preserved output, so the test fails.【F:test_results.txt†L2620-L2634】【F:theo/services/api/app/ai/ledger.py†L578-L972】
- **Impact:** The test suite is out of sync with the ledger’s new semantics for transient errors and does not exercise the intended deduplication path.
- **Suggested actions:** Update the test to simulate the current recovery strategy (e.g., wait for a preserved success record) or revise the ledger logic if the new exception is unintended.

## Fragile dependency on a private ingestion helper
- `test_ingest_markdown_with_windows_1252_bytes` directly calls `ingest_pipeline._parse_text_file`, a private alias that was renamed in the service module. In environments where the alias is missing (e.g., older wheels or reload scenarios), the test crashes with `AttributeError` before asserting anything.【F:tests/api/test_ingest_uploads.py†L135-L210】【F:test_results.txt†L2655-L2880】
- Although the current source tree re-exports `_parse_text_file`, relying on a private attribute keeps the test brittle and sensitive to refactors or import-order glitches.【F:theo/services/api/app/ingest/pipeline.py†L60-L88】
- **Suggested actions:** Move the assertions to the public `parse_text_file` helper or expose a supported testing hook to keep the contract stable.

## Heavy optional dependencies imported during test collection
- Importing `theo.services.api.app.main` during test discovery pulls in the full ingestion stack, which imports `FlagEmbedding`, `transformers`, and ultimately `torch`. Even a targeted test run spends significant time loading GPU inference modules before the first assertion executes.【F:tests/api/conftest.py†L18-L25】【a2291f†L1-L116】
- **Impact:** Local feedback loops slow to a crawl, and environments without torch fail before tests can start.
- **Suggested actions:** Gate heavyweight imports behind runtime flags (similar to `_skip_heavy_startup`) or lazy-load optional ML dependencies only when specific tests require them.

## Reading the test durations report
- Pytest now emits a summary of the 50 slowest tests after each run. Look for the "slowest durations" table near the end of the output to spot newly sluggish cases quickly.
- Re-run the suite with `pytest -q` to view the report again; combine it with markers such as `-m "not slow"` when you want to narrow in on targeted failures without losing the timing context.
