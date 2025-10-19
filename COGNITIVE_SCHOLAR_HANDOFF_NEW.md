# Cognitive Scholar CS-003 Handoff (Fresh Chat)

## Summary
- **Current focus**: CS-003 Live Plan Panel backend plumbing.
- **Status**: Research loop now persists live plan state; chat responses surface `plan` snapshots. Plan API routes, streaming, frontend wiring, and tests remain open.

## Completed Work
- **Plan DTO integration**: `ResearchLoopController` now builds and synchronises `ResearchPlan` instances, with helpers for reorder/update/skip mutations (`theo/services/api/app/ai/research_loop.py`).
- **Chat response enrichment**: `chat_turn()` and `_serialise_chat_session()` return the active plan via `ChatSessionResponse.plan` / `ChatSessionState.plan` (`theo/services/api/app/routes/ai/workflows/chat.py`).
- **Schema updates**: Added optional `plan` field to relevant API models (`theo/services/api/app/models/ai.py`).
- **Plan CRUD endpoints**: Added plan GET, reorder, update, and skip routes backed by controller helpers (`theo/services/api/app/routes/ai/workflows/chat.py`).

## Outstanding Tasks
- **Streaming updates**: Refactor `/chat` endpoint to emit plan deltas (NDJSON or SSE) so UI stays live.
- **Frontend integration**: Extend `api-normalizers.ts` & chat client events to ingest `plan` snapshots/events for `PlanPanel.tsx`.
- **Testing**: Cover controller mutations, new plan routes, and streaming behaviour; update docs (`docs/tasks/TASK_005_Cognitive_Scholar_MVP_Tickets.md`).

## Suggested Next Steps
1. Implement plan CRUD routes in `chat.py`, returning updated `ResearchPlan` payloads.
2. Adjust chat workflow response/streaming to emit `{"type":"plan_update"}` events alongside answer tokens.
3. Wire frontend normalisers + store updates; ensure `PlanPanel.tsx` consumes state.
4. Backfill unit/integration tests; document CS-003 progress.

## Verification Notes
- Run targeted FastAPI route tests once plan endpoints exist.
- Execute chat turn happy path to confirm `plan` snapshot appears in JSON response.
- Add streaming smoke test after NDJSON integration.

## Key Files Reference
- **Controller** `theo/services/api/app/ai/research_loop.py`: Exposes `ResearchPlan` lifecycle helpers (`enqueue`, `update_step`, `reorder`, `skip`).
- **Chat Routes** `theo/services/api/app/routes/ai/workflows/chat.py`: Hosts `/chat` POST + (future) `/chat/{session_id}/plan` routes.
- **API Models** `theo/services/api/app/models/ai.py`: Provides `ChatSessionResponse.plan` and mutation payload schemas.
- **Frontend Store** `theo/services/web/app/chat/state/planStore.ts`: Centralises plan state, ready for streaming/event ingestion.
- **Plan Panel UI** `theo/services/web/app/chat/PlanPanel.tsx`: Renders live plan list; currently expects static prop injection.

## Implementation Outline
1. **Surface CRUD endpoints**: Add GET/PATCH/POST/DELETE handlers under `/chat/{session_id}/plan` delegating to `ResearchLoopController`.
2. **Emit streaming deltas**: Extend `/chat` workflow to push `{"type":"plan_update"}` frames for enqueue/reorder/skip actions.
3. **Frontend wiring**: Normalise `plan` payloads in `api-normalizers.ts`, hydrate store, and subscribe Plan Panel to streaming events.
4. **Testing & docs**: Add controller + route tests, streaming contract tests, and update `docs/tasks/TASK_005_Cognitive_Scholar_MVP_Tickets.md`.

## Risks & Mitigations
- **Race conditions**: Concurrent plan mutations via chat and explicit CRUD can drift. Enforce controller-level locks or optimistic version checks.
- **Streaming payload size**: Large plans may bloat SSE. Consider diff-based messages (`added`, `updated`, `removed`).
- **Frontend desync**: Ensure Plan Panel falls back to periodic GET if streaming disconnects.

## Progress Tracking
- [x] Persist plan state via controller + DTOs.
- [x] Expose dedicated plan CRUD endpoints.
- [ ] Stream live plan updates alongside chat tokens.
- [ ] Integrate Plan Panel with normalised plan store + events.
- [ ] Backfill unit/integration coverage + docs.
