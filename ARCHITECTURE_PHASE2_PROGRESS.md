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

## Entry – 2025-10-27

### Delivered in this PR
- Restored the legacy `theo.services.api.app.ai` surface by re-exporting the guardrailed RAG workflow helpers (`run_guarded_chat`, `generate_sermon_prep_outline`, etc.) and the commonly imported submodules so existing routes and tests resolve the new package layout without import errors.

### Follow-up / Remaining Scope for Phase 2
1. **Continue migrating the workflow implementations into modular subpackages:**
   - Move remaining guardrail responses and prompt builders from `ai/rag/workflow.py` into purpose-specific modules (e.g., `ai/rag/deliverables.py`, `ai/rag/prompts.py`) to shrink the monolith.
   - Audit the FastAPI routes for any direct `models.ai` dependencies that still need shims while the migration completes.
2. **Strengthen async client parity:**
   - Port retry/backoff logic and cache usage from `legacy_clients.py` into the async adapters so callers can begin switching over without behavioural regressions.
3. **Expand targeted tests for the compatibility layer:**
   - Add regression tests around the package re-exports (e.g., importing `run_guarded_chat` from `theo.services.api.app.ai`) to prevent future refactors from accidentally dropping the shim again.

### Guidance for the Next Agent
- Prefer adding new workflow helpers directly into the modular `ai/rag/` structure and simply re-export them from `ai/__init__.py` as needed for backwards compatibility.
- Keep the compatibility shim lean by deleting exports once upstream call sites finish migrating to the new modules, ensuring the package surface reflects the final architecture when Phase 2 closes.

## Entry – 2025-10-28

### Delivered in this PR
- Added regression tests under `tests/api/ai/test_ai_package_exports.py` to ensure the modular AI package continues to re-export guardrailed workflow helpers and legacy submodules relied on by existing routes/tests.

### Follow-up / Remaining Scope for Phase 2
1. **Continue decomposing the RAG workflow monolith:**
   - Split remaining guardrail responses and prompt builders out of `ai/rag/workflow.py` into focused modules, updating the package exports once the new structure is in place.
   - Track FastAPI routes still importing from `models.ai` so they can be migrated to the new modules in tandem.
2. **Strengthen async client parity:**
   - Port retry/backoff logic and cache usage from `legacy_clients.py` into the async adapters so callers can begin switching over without behavioural regressions.
   - Backfill tests that exercise both the compatibility shim and the async clients as feature parity improves.
3. **Harden compatibility shims and guardrails:**
   - Maintain the new regression tests as additional exports move; extend coverage to new compatibility surfaces as they appear.
   - Remove shimmed exports once call sites finish migrating to the modular structure to keep the package surface aligned with the target architecture.

### Guidance for the Next Agent
- Keep expanding the modular `ai/rag/` structure by moving workflow responsibilities into smaller, purpose-driven modules and updating the compatibility re-exports to match.
- When migrating workflow helpers or clients, update the regression tests (and add new ones) so the compatibility guarantees are enforced automatically.
- Continue appending to this log after each PR with concrete deliverables and next steps for Phase 2.

## Entry – 2025-10-29

### Delivered in this PR
- Extracted the guardrail refusal builders into `theo/services/api/app/ai/rag/refusals.py` and wired the package proxy to keep the new module patchable for compatibility shims.
- Refactored the guarded answer pipeline to reuse `PromptContext` for prompt/summary construction, eliminating duplicated guardrail sanitisation logic in `workflow.py`.

### Follow-up / Remaining Scope for Phase 2
1. **Broaden the prompt utilities:**
   - Migrate the remaining workflow-specific prompt builders (e.g., sermon prep, multimedia) into `ai/rag/prompts.py` so the module owns all sanitisation flows.
   - Consider exposing PromptContext helpers for non-RAG workflows to simplify future refactors.
2. **Harden guardrail refusal behaviours:**
   - Add targeted unit coverage for `refusals.build_guardrail_refusal` to validate catalogue fallback behaviour against empty/errored database lookups.
   - Audit downstream call sites to delete any lingering direct imports from `workflow.py` once they consume the new module directly.
3. **Continue decomposing the RAG workflow monolith:**
   - Identify additional guardrail response helpers still embedded in `workflow.py` and migrate them into purpose-built modules (e.g., deliverables, guardrail states).
   - Ensure regression tests cover each new module as exports move to keep compatibility stable.

### Guidance for the Next Agent
- When moving more workflow helpers, keep updating the regression tests and package proxy (`ai/rag/__init__.py`) so the shims remain patchable from the old import paths.
- Prefer funnelling any new guardrail response logic through the `refusals` module to keep `workflow.py` focused on orchestration rather than response shaping.
- Continue appending to this log after each PR with precise deliverables and outstanding scope to maintain continuity through the migration.

## Entry – 2025-10-30

### Delivered in this PR
- Added regression coverage for `ai/rag/refusals.build_guardrail_refusal`, exercising the database-backed citation path and the static fallback to guard against future regressions while the guardrail catalogue evolves.

### Follow-up / Remaining Scope for Phase 2
1. **Extend guardrail refusal behaviours:**
   - Backfill tests for refusal telemetry/logging once the guardrail service exposes structured events.
   - Cover negative-path validation (e.g., malformed guardrail profiles) as new inputs are formalised.
2. **Continue modularising the RAG workflows:**
   - Move remaining response-shaping helpers (key point selection, devotional builders) out of `workflow.py` into dedicated modules now that regression tests protect the refusal layer.
3. **Broaden prompt utility adoption:**
   - Shift the sermon prep and multimedia prompt builders into `ai/rag/prompts.py`, updating the new tests as needed to reflect the sanitisation pipeline.

### Guidance for the Next Agent
- Keep the new refusal tests updated as guardrail catalogue storage changes; they provide fast feedback that the compatibility shim still yields stable refusals when the database is unavailable.
- Use the upcoming modular splits to tighten `ai/__init__.py` exports only after routes/tests adopt the new module boundaries to preserve compatibility during the migration.
- Continue appending to this log after each PR with precise deliverables and outstanding scope to maintain continuity through the migration.

## Entry – 2025-10-31

### Delivered in this PR
- Moved the revision gating and schema translation helpers into the new `theo/services/api/app/ai/rag/revisions.py` module so the guarded workflow no longer owns that logic directly.
- Updated the guarded answer pipeline to consume the extracted helpers and trimmed unused imports that lingered from the legacy implementation.
- Added focused tests under `tests/api/ai/test_rag_revisions.py` covering revision triggering and schema conversion to keep the new boundary protected as the module evolves.

### Follow-up / Remaining Scope for Phase 2
1. **Continue shrinking the RAG workflow module:**
   - Identify the remaining orchestration-adjacent helpers (e.g., deliverable wrappers, devotional builders) that can join purpose-built modules similar to `revisions.py`.
   - Keep the regression imports in `ai/__init__.py` aligned as functions move so compatibility shims stay intact.
2. **Broaden prompt utility adoption:**
   - Finish relocating the sermon prep and multimedia prompt builders into `ai/rag/prompts.py`, ensuring routes and tests adopt the shared sanitisation helpers.
   - Revisit the RAG regression tests once the prompt refactor lands to confirm the revised contexts are exercised.
3. **Exercise the revision path end-to-end:**
   - Add integration coverage that drives a critique through to a revision when the async adapters gain parity, proving the new module wiring holds under real completions.
   - Capture telemetry assertions for revision events to guarantee analytics remain accurate during the migration.

### Guidance for the Next Agent
- Keep migrating small helper clusters out of `workflow.py` to preserve momentum—`revisions.py` can serve as the pattern for where to land them.
- When moving prompt builders or deliverable wrappers, update both the compatibility exports and regression tests in the same PR to avoid breaking legacy import paths.
- Continue appending to this log after every Phase 2 PR with the same structure so the ongoing hand-off remains easy to follow.

## Entry – 2025-11-01

### Delivered in this PR
- Extracted the sermon prep, devotional, multimedia digest, and comparative analysis workflow wrappers into the new `theo/services/api/app/ai/rag/deliverables.py` module to shrink `workflow.py` and align with the modular guardrail architecture.
- Updated the RAG package proxy (`theo/services/api/app/ai/rag/__init__.py`) and workflow shim to import from the new module so existing imports (including regression tests) continue to resolve without code changes.
- Ran the compatibility regression suite to confirm the new module layout still surfaces all exported workflows relied on by the API layer.

### Follow-up / Remaining Scope for Phase 2
1. **Continue decomposing `workflow.py`:**
   - Migrate remaining orchestration-adjacent helpers (e.g., corpus curation, research reconciliation, verse copilot) into purpose-built modules similar to `deliverables.py` and `revisions.py`.
   - Remove the compatibility aliases from `workflow.py` once routes/tests import the new modules directly, keeping the shim minimal.
2. **Harmonise module proxies and tests:**
   - Extend the regression coverage in `tests/api/ai/test_ai_package_exports.py` (or adjacent suites) to assert the new `deliverables` module stays wired through the proxy during future moves.
   - Ensure `_RAGModule` mirrors additional submodules as they emerge so dynamic patching remains reliable in tests.
3. **Prep for prompt builder relocation:**
   - With deliverables separated, plan the relocation of workflow-specific prompt helpers into `ai/rag/prompts.py`, verifying `PromptContext` continues to feed the guardrailed pipeline end-to-end.

### Guidance for the Next Agent
- When moving more workflow helpers, add imports to the proxy module (`ai/rag/__init__.py`) at the same time so downstream modules retain their existing import paths.
- Keep running the API export regression tests after each migration step—they provide fast feedback that the compatibility surface is intact while the package splits continue.
- Continue appending entries to this log after every Phase 2 PR to maintain the shared hand-off narrative.

## Entry – 2025-11-02

### Delivered in this PR
- Moved the verse copilot, corpus curation, and research reconciliation orchestrators into dedicated modules under `theo/services/api/app/ai/rag/` (`verse.py`, `corpus.py`, `collaboration.py`) to continue slimming `workflow.py`.
- Added compatibility shims that delegate from `workflow.py` to the new modules and expanded the RAG package proxy so patches still reach the relocated implementations.
- Extended the AI package export regression test to cover the newly modularised workflows, ensuring the compatibility layer remains exercised as functions move.

### Follow-up / Remaining Scope for Phase 2
1. **Continue decomposing `workflow.py`:**
   - Identify the remaining orchestration helpers (e.g., chat streaming, verse follow-up generation, research digest formatting) that can relocate into focused modules once supporting abstractions are ready.
   - Remove the temporary delegation wrappers in `workflow.py` after downstream call sites import from the new modules directly.
2. **Align package proxies with future modules:**
   - Update `_RAGModule` and related shims whenever additional modules are introduced so monkeypatched attributes still propagate during tests.
   - Consider surfacing explicit module exports (e.g., `rag.verse`) once the compatibility surface stabilises to ease targeted imports.
3. **Backfill targeted tests for relocated workflows:**
   - Add unit or integration coverage around `verse.generate_verse_brief`, `corpus.run_corpus_curation`, and `collaboration.run_research_reconciliation` as soon as lightweight fixtures exist to validate their behaviour outside of package export checks.

### Guidance for the Next Agent
- Prefer landing new workflow refactors directly inside the purpose-built modules and keep the compatibility wrappers lightweight until legacy imports are updated.
- When introducing additional modules, update both the package proxy and regression tests in the same PR to keep the compatibility guarantees verifiable.
- Continue appending entries to this log after every Phase 2 PR so the migration narrative stays unbroken.

## Entry – 2025-11-03

### Delivered in this PR
- Extracted the guardrailed chat pipeline (`GuardedAnswerPipeline`, `_guarded_answer`, `_guarded_answer_or_refusal`, and `run_guarded_chat`) into the new `theo/services/api/app/ai/rag/chat.py` module so the remaining legacy logic in `workflow.py` is isolated behind a shim.
- Rebuilt `theo/services/api/app/ai/rag/workflow.py` as a compatibility proxy that forwards attribute mutations to the chat module while continuing to re-export the legacy surface for existing imports and tests.
- Updated the RAG package proxy and downstream modules (`deliverables.py`, `collaboration.py`, `verse.py`) to depend on the new chat module and added lazy workflow imports for retrieval helpers to keep monkeypatch-based tests working. Extended the targeted API workflow tests to confirm the new layout passes.

### Follow-up / Remaining Scope for Phase 2
1. **Continue teasing apart the chat pipeline internals:**
   - Move cache instrumentation, telemetry logging, and reasoning helpers from `chat.py` into narrower modules (`cache.py`, `telemetry.py`, `reasoning.py`) as the new architecture solidifies.
   - Replace direct imports of deliverable builders with dependency-injected hooks so the chat pipeline no longer depends on deliverable modules at import time.
2. **Trim the compatibility layer once call sites migrate:**
   - Audit FastAPI routes and tests to import from `rag.chat` (or other new modules) directly so `workflow.py` can eventually stop re-exporting its legacy surface.
   - Add regression coverage that patches `rag.chat` directly to guard against missing proxy updates when the compatibility shim is removed.
3. **Harmonise retrieval shims and fixtures:**
   - Consolidate the lazy `workflow.search_passages` imports added to deliverables into a shared helper or fixture utility so future modules can stub retrieval without new boilerplate.
   - Evaluate whether the RAG package proxy should propagate attribute patches to the retrieval module to simplify monkeypatching semantics.

### Guidance for the Next Agent
- Keep updating both the compatibility shim and the package proxy whenever new modules are introduced so monkeypatch-heavy tests continue to work during the migration.
- When relocating helpers out of `chat.py`, add focused tests around the new modules and adjust the lazy imports in deliverables/verse/collaboration at the same time to avoid circular imports.
- Continue appending entries to this log with the same structure after each Phase 2 PR to preserve the migration narrative and highlight remaining blockers.

## Entry – 2025-11-04

### Delivered in this PR
- Split the guardrailed chat pipeline internals by moving cache telemetry helpers into `ai/rag/cache.py` and creating new `ai/rag/telemetry.py` and `ai/rag/reasoning.py` modules that encapsulate span handling, workflow logging, and the critique/revision flow.
- Refactored `ai/rag/chat.py` to depend on the new helpers, trimming inline instrumentation, reusing shared cache status emitters, and routing critique/revision through the dedicated reasoning module while keeping recorder hooks intact.
- Replaced direct workflow logging with telemetry helpers across the chat entrypoints and ran the export regression suite (`tests/api/ai/test_ai_package_exports.py`) to confirm the compatibility surface still passes.

### Follow-up / Remaining Scope for Phase 2
1. **Finish decoupling deliverable dependencies from `chat.py`:**
   - Introduce dependency-injected hooks (or service interfaces) for deliverable builders so the chat pipeline no longer imports `deliverables.py` at module import time.
   - Add targeted tests covering the injection path once the abstraction lands to ensure recorder logging remains stable.
2. **Harden the new telemetry/reasoning helpers:**
   - Backfill unit coverage for `rag.telemetry` and `rag.reasoning` to lock down expected event payloads, especially cache status propagation and revision logging.
   - Evaluate whether additional guardrail failure metadata should be surfaced through the telemetry helpers for downstream analytics.
3. **Continue slimming the compatibility layer:**
   - Audit remaining modules that still import the legacy workflow surface and update them to reference the new helpers directly so future PRs can shrink `rag/workflow.py` further.
   - Capture regression checks that patch `rag.telemetry`/`rag.reasoning` directly to ensure the proxy module mirrors new exports as they land.

### Guidance for the Next Agent
- Keep new guardrailed workflow helpers inside the purpose-built `ai/rag/` modules and re-export only what legacy call sites need from `ai/__init__.py` until migrations complete.
- When wiring dependency injection for deliverable builders, update both the FastAPI routes and the recorder expectations in the same PR to avoid transient import loops.
- Continue appending entries to this log after each PR so Phase 2 progress and outstanding blockers remain easy to track.

## Entry – 2025-11-05

### Delivered in this PR
- Introduced a `DeliverableHooks` configuration API in `ai/rag/chat.py` so the chat pipeline no longer imports the deliverable builders at module import time while keeping backwards-compatible exports available for legacy call sites.
- Updated the `ai/rag/workflow.py` proxy to install the deliverable hooks during initialisation, ensuring the compatibility shim mirrors the relocated helpers without reintroducing tight coupling.
- Added a dedicated unit test (`tests/api/ai/test_chat_deliverable_hooks.py`) that exercises the hook registration path to guard against future regressions in the compatibility surface.

### Follow-up / Remaining Scope for Phase 2
1. **Complete deliverable dependency decoupling downstream:**
   - Audit modules that still import deliverable helpers via the chat proxy (routes, workers) and migrate them to import from `ai.rag.deliverables` directly once the compatibility layer stabilises.
   - Remove the temporary placeholder functions from `chat.py` after all call sites resolve the new hook wiring.
2. **Harden the new telemetry/reasoning helpers:**
   - Backfill unit coverage for `rag.telemetry` and `rag.reasoning` to lock down expected event payloads, especially cache status propagation and revision logging.
   - Evaluate whether additional guardrail failure metadata should be surfaced through the telemetry helpers for downstream analytics.
3. **Continue slimming the compatibility layer:**
   - Audit remaining modules that still import the legacy workflow surface and update them to reference the new helpers directly so future PRs can shrink `rag/workflow.py` further.
   - Capture regression checks that patch `rag.telemetry`/`rag.reasoning` directly to ensure the proxy module mirrors new exports as they land.

### Guidance for the Next Agent
- Prefer importing deliverable builders from the new module namespaces in upcoming PRs so we can eventually delete the compatibility exports from `chat.py` once all call sites migrate.
- When expanding telemetry/reasoning coverage, update the regression tests and proxy exports concurrently to keep the monkeypatch-based suites stable during refactors.
- Continue appending entries to this log with concrete deliverables and blockers after each Phase 2 PR to maintain the shared hand-off narrative.
