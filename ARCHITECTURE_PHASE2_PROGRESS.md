# Theoria Architecture Phase 2 – Progress Log

> **Update cadence:** Update this log at the end of every Phase 2 PR. Each entry should capture (1) changes delivered, (2) remaining scope, and (3) guidance for the next implementer. Keep this document as the canonical hand-off reference until Phase 2 is complete.

## Entry – 2025-10-24

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


## Current Entry – 2025-10-25

### Delivered in this PR
- Carved the guardrail catalogue and advisory Pydantic schemas out of `models/ai.py` into the new `theo/services/api/app/ai/guardrails/` package so the Phase 2 guardrail module has a concrete home.
- Updated the `/ai/features` and guardrail workflow routes to consume the new abstractions without changing their response payloads.

### Follow-up / Remaining Scope for Phase 2
1. **Finish the guardrail package build-out:**
   - Migrate the HTTP response helpers in `routes/ai/workflows/guardrails.py` into the new `ai/guardrails/` namespace once the package gains more structure (e.g., advice builders, refusal templates).
   - Wire future guardrail configuration sources (DB/feature flags) through the new package instead of hard-coding catalogues.
2. **Continue slimming `models/ai.py`:**
   - Move the LLM registry request/response schemas and related helpers into purpose-built modules under `ai/registry`.
   - Audit remaining chat/memory schemas for relocation into `ai/` subpackages as their owning services come online.
3. **Unblock test harness imports:**
   - `tests/api` cannot import the FastAPI app because `theo.services.api.app.ai.registry` still points at `theo.services.api.app.ai.clients` (package) which does not expose `build_client` from the legacy module.
   - Either finish migrating the factory logic into `ai/clients/` or introduce a compatibility shim so the new registry helpers can resolve their client factory.

### Guidance for the Next Agent
- Consolidate future guardrail schema changes inside `theo/services/api/app/ai/guardrails/` and delete the legacy definitions from `models/ai.py` as additional call sites move over.
- When tackling the client factory import conflict, ensure `registry.py` continues to surface a provider-agnostic `build_client` for the rest of the service layer before deleting the legacy module.
- Keep updating this log after every PR so we maintain a continuous hand-off narrative across the remaining Phase 2 scope.

## Entry – 2025-10-26

### Delivered in this PR
- Renamed the legacy `theo.services.api.app.ai.clients` module to `legacy_clients.py` and updated the new `ai/clients/` package to re-export the existing client factory API so `registry.py` and the API tests can import `build_client` again without touching legacy call sites.
- Added explicit compatibility exports for the legacy client helpers alongside the nascent async adapters (`AsyncOpenAIClient`, `AsyncAnthropicClient`) so Phase 2 work can continue migrating functionality piecemeal.

### Follow-up / Remaining Scope for Phase 2
1. **Finish decomposing the legacy client monolith:**
   - Gradually migrate provider adapters, caching utilities, and prompt helpers from `ai/legacy_clients.py` into purpose-built modules under `ai/clients/` while keeping `__init__.py` shimmed for backwards compatibility.
   - Once call sites no longer rely on the legacy implementations, delete `legacy_clients.py` and collapse the compatibility layer.
2. **Resolve missing AI surface exports blocking tests:**
   - `tests/api` still fail because `theo.services.api.app.ai` no longer exposes `run_guarded_chat`; either re-home the workflow utilities into the new package or update the routes/tests to consume the new abstractions.
   - Audit other guardrail/chat helpers referenced by the FastAPI routes to ensure imports remain stable during the migration.
3. **Align the async client adapters with the legacy interfaces:**
   - Flesh out the async `clients/` implementations so they can satisfy the `LanguageModelClientProtocol` expectations and replace the synchronous legacy clients without regression.
   - Expand unit coverage to exercise both the compatibility shim and the new async adapters once they reach feature parity.

### Guidance for the Next Agent
- Keep the compatibility exports in `ai/clients/__init__.py` up to date as you migrate symbols out of `legacy_clients.py`; this prevents regressions for modules still importing `theo.services.api.app.ai.clients`.
- When porting workflow helpers, coordinate with the FastAPI route owners so the import paths change only after the new modules are wired end-to-end.
- Continue appending entries to this log with concrete deliverables and blockers after each PR to maintain the Phase 2 hand-off narrative.
