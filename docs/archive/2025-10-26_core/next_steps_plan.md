> **Archived on 2025-10-26**

# Proposed Next Steps

## 1. Stabilize contradiction seed migrations
- **Why**: API startup currently fails in tests because the SQLite schema lacks the `perspective` column required by `ContradictionSeed`, preventing the seeding routine from completing. This blocks every endpoint that depends on application startup. 
- **What to do**:
  - Ensure the SQLite migration that introduces `contradiction_seeds.perspective` runs (or an equivalent schema sync) when API tests create fresh databases.
  - Keep the defensive fallback in `seed_contradiction_claims` but extend it so the seeder skips gracefully even if migrations are bypassed entirely.
  - Add a regression test that covers startup with migrations disabled to guard against future schema drift.
- **References**: `test_results.txt` for the failure trace and the seeding logic in `theo/services/api/app/db/seeds.py`.

## 2. Harden ingest URL error handling
- **Why**: The ingest URL tests expect deterministic 400-level responses for slow responses, oversized payloads, and redirect loops, but the current implementation bubbles up 500-level debug reports instead.
- **What to do**:
  - Wrap the `fetch_web_document` read loop in targeted exception handling that translates timeouts, size overruns, and redirect loop detections into `UnsupportedSourceError` responses.
  - Add coverage for oversized payloads and redirect loop scenarios so that the handler maintains consistent error semantics.
  - Verify network guardrails (blocked hosts, IP ranges, redirect depth) remain enforced after the change.
- **References**: Failure details in `test_results.txt` and existing guard implementations in `theo/services/api/app/ingest/network.py`.

## 3. Fix AI router inflight deduplication
- **Why**: `test_router_deduplicates_inflight_requests` fails because deduplicated requests exit without a cached result, raising `GenerationError`. This undermines the router’s load-shedding guarantees under concurrency.
- **What to do**:
  - Audit `Ledger.wait_for_inflight` to ensure that deduplicated workers either receive the cached completion or resubscribe until the original generation finishes.
  - Add instrumentation around inflight transitions to detect and clean up stale rows before reporting errors.
  - Expand router tests to cover the “restart” and “late cache write” paths so future refactors keep deduplication stable.
- **References**: The failing assertion in `test_results.txt` and the inflight ledger logic in `theo/services/api/app/ai/ledger.py`.
