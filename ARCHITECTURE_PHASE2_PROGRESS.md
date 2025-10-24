# Theoria Architecture Phase 2 – Progress Log

> **Update cadence:** Update this log at the end of every Phase 2 PR. Each entry should capture (1) changes delivered, (2) remaining scope, and (3) guidance for the next implementer. Keep this document as the canonical hand-off reference until Phase 2 is complete.

## Current Entry – 2025-10-24

### Delivered in this PR
- Established the new modular AI package scaffold under `theo/services/api/app/ai/`, including provider-agnostic interfaces, client factory plumbing, and supporting cache/usage utilities.
- Added provider-specific client adapters for OpenAI and Anthropic with optional dependency guards to avoid import failures in lean environments.
- Implemented the `SafeAIRouter` with concurrency-safe request deduplication, TTL caching, and usage tracking hooks.

### Follow-up / Remaining Scope for Phase 2
1. **Migrate existing logic out of `theo/services/api/app/models/ai.py`:**
   - Audit the current 18K-line module and incrementally extract functionality into the new package (`clients`, `routing`, `guardrails`, `ledger`, `cache`, etc.).
   - Replace legacy imports throughout the codebase to consume the new abstractions.
   - Delete or drastically slim down `models/ai.py` once all call sites are migrated.
2. **Introduce guardrail and ledger submodules:**
   - Populate `theo/services/api/app/ai/guardrails/` (directory not yet created) with validation, safety, and prompt governance components referenced in the architecture plan.
   - Extend the usage tracker to persist metrics once requirements are clarified.
3. **Test harness optimization and API refactors:**
   - The legacy `tests/conftest.py` remains unchanged; implement the proposed lightweight fixtures and dependency mocks, ensuring existing regression helpers continue to work.
   - Proceed with the main application factory decomposition and error handling unification described in the Phase 2 checklist.

### Guidance for the Next Agent
- Before starting new work, read this file and append your own section using the same headings. Keep prior entries intact so we retain a running log.
- Coordinate module migrations carefully: move logic in manageable chunks and keep interfaces backward compatible until all call sites are switched.
- Update this log at the end of your PR with a precise summary of what changed and what remains.

