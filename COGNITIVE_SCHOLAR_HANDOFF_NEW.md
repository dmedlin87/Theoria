# Cognitive Scholar CS-003 Handoff (Fresh Chat)

## Summary
- **Current focus**: CS-003 Live Plan Panel scaffolding.
- **Status**: Research loop persists live plan state and chat responses include `plan` snapshots. Plan API routes, streaming, frontend wiring, and tests still outstanding.

## Completed Work
- **Plan DTO integration**: `ResearchLoopController` builds and persists `ResearchPlan` instances with helpers for enqueue/reorder/update/skip mutations (`theo/services/api/app/ai/research_loop.py`).
- **Chat response enrichment**: `chat_turn()` and `_serialise_chat_session()` now include the active plan in `ChatSessionResponse.plan` / `ChatSessionState.plan` snapshots (`theo/services/api/app/routes/ai/workflows/chat.py`).
- **Schema updates**: Optional `plan` fields have been added to API response models (`theo/services/api/app/models/ai.py`).

## Outstanding Tasks
- **Plan routes**: Add REST handlers (`GET /chat/{session_id}/plan`, mutate/reorder/skip endpoints) that wrap controller helpers and persist updates.
- **Streaming updates**: Refactor `/chat` to emit plan deltas (NDJSON or SSE) so the UI stays in sync while the loop runs.
- **Frontend integration**: Create `PlanPanel` component + client store, extend normalisers to ingest `plan` snapshots/events, and wire to chat workspace.
- **Testing & docs**: Cover controller mutations, plan routes, and streaming behaviour; update CS-003 ticket status in `docs/tasks/TASK_005_Cognitive_Scholar_MVP_Tickets.md`.

## Suggested Next Steps
1. Implement plan CRUD routes in `chat.py`, returning updated `ResearchPlan` payloads on each mutation.
2. Adjust chat workflow streaming to emit `{"type":"plan_update"}` frames alongside answer tokens.
3. Build the Plan Panel UI + state store, ensuring chat clients hydrate from snapshots and streaming deltas.
4. Backfill unit/integration tests and document CS-003 progress in the task tracker.

## Verification Notes
- Run targeted FastAPI route tests once plan endpoints exist.
- Execute chat turn happy path to confirm `plan` snapshots return correctly.
- Add streaming smoke test after NDJSON/SSE integration.

## Key Files Reference
- **Controller** `theo/services/api/app/ai/research_loop.py`: Exposes `ResearchPlan` lifecycle helpers (`enqueue`, `update_step`, `reorder`, `skip`).
- **Chat Routes** `theo/services/api/app/routes/ai/workflows/chat.py`: Hosts `/chat` POST; needs `/chat/{session_id}/plan` family.
- **API Models** `theo/services/api/app/models/ai.py`: Provides `ChatSessionResponse.plan` and mutation payload schemas.
- **Frontend scaffolding**: `theo/services/web/app/chat/` (workspace/hooks) — add store + `PlanPanel` component alongside timeline UI.

## Implementation Outline
1. **Surface CRUD endpoints**: Add GET/PATCH/POST/DELETE handlers under `/chat/{session_id}/plan` delegating to `ResearchLoopController`.
2. **Emit streaming deltas**: Extend `/chat` workflow to push `{"type":"plan_update"}` frames for enqueue/reorder/skip actions.
3. **Frontend wiring**: Normalise `plan` payloads client-side, hydrate a dedicated plan store, and subscribe the Plan Panel to streaming events.
4. **Testing & docs**: Add controller + route tests, streaming contract tests, and update `docs/tasks/TASK_005_Cognitive_Scholar_MVP_Tickets.md`.

## Risks & Mitigations
- **Race conditions**: Concurrent plan mutations via chat and explicit CRUD can drift. Enforce controller-level locks or optimistic version checks.
- **Streaming payload size**: Large plans may bloat SSE. Consider diff-based messages (`added`, `updated`, `removed`).
- **Frontend desync**: Ensure Plan Panel falls back to periodic GET if streaming disconnects.

## Progress Tracking
- [x] Persist plan state via controller + DTOs.
- [ ] Expose dedicated plan CRUD endpoints.
- [ ] Stream live plan updates alongside chat tokens.
- [ ] Integrate Plan Panel with normalised plan store + events.
- [ ] Backfill unit/integration coverage + docs.

## Known Limitations & Bugs
- No open bugs logged. Add new issues to `docs/status/KnownBugs.md` and reference their IDs here.
