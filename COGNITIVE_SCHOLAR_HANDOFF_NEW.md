# Cognitive Scholar CS-003 Handoff (Fresh Chat)

## Summary
- **Current focus**: Finishing CS-003 by layering in streaming plan telemetry.
- **Status**: Plan CRUD endpoints, chat response snapshots, and the Plan Panel UI are shipped. Streaming deltas are the remaining gap for real-time sync.

## Completed Work
- **Plan DTO integration**: `ResearchLoopController` builds and persists `ResearchPlan` instances with helpers for enqueue/reorder/update/skip mutations (`theo/services/api/app/ai/research_loop.py`).
- **Chat response enrichment**: `chat_turn()` and `_serialise_chat_session()` now include the active plan in `ChatSessionResponse.plan` / `ChatSessionState.plan` snapshots (`theo/services/api/app/routes/ai/workflows/chat.py`).
- **Schema updates**: Optional `plan` fields have been added to API response models (`theo/services/api/app/models/ai.py`).

## Outstanding Tasks
- **Streaming updates**: Refactor `/ai/chat` streaming responses to emit incremental plan frames so the panel updates mid-loop.
- **Loop event hooks**: Decide whether intermediate loop actions (pause/step/skip) should push plan deltas or rely on polling.
- **Observability**: Add metrics/logging for plan mutations to monitor reorder/update/skip usage.

## Suggested Next Steps
1. Extend the streaming pipeline to emit lightweight `plan_update` frames (diffs or snapshots) during long-running loops.
2. Update the Plan Panel store to consume streaming deltas and fall back to periodic refresh when streams are unavailable.
3. Instrument plan mutations with structured logs/metrics to validate usage patterns and detect race conditions.

## Verification Notes
- Run targeted FastAPI route tests once plan endpoints exist.
- Execute chat turn happy path to confirm `plan` snapshots return correctly.
- Add streaming smoke test after NDJSON/SSE integration.

- **Controller** `theo/services/api/app/ai/research_loop.py`: Plan lifecycle helpers and default sequence logic.
- **Chat Routes** `theo/services/api/app/routes/ai/workflows/chat.py`: `/chat/{session_id}/plan` CRUD endpoints + plan snapshots in chat responses.
- **API Models** `theo/services/api/app/models/ai.py`: `ResearchPlan` models and chat response fields.
- **Frontend** `theo/services/web/app/chat/ChatWorkspace.tsx`: Hydrates plan state, wires `PlanPanel`, and drives plan mutations.
- **UI Component** `theo/services/web/app/components/PlanPanel.tsx`: Live plan panel with reorder/edit/skip controls.
- **Client libraries** `theo/services/web/app/lib/{api-client,api-normalizers,chat-client}.ts`: Plan fetch/mutation helpers and streaming payloads.

## Implementation Outline
1. **Plan streaming**: Define `plan_update` payload contract and emit from `/ai/chat` streaming loop.
2. **Client handling**: Consume streaming updates in `ChatWorkspace`/`PlanPanel`, reconciling with optimistic local state.
3. **Resilience**: Fall back to periodic plan fetch (existing REST endpoints) when streaming is unavailable.
4. **QA**: Add streaming-focused tests once deltas ship (unit + integration).

## Risks & Mitigations
- **Race conditions**: Concurrent plan mutations via chat and explicit CRUD can drift. Enforce controller-level locks or optimistic version checks.
- **Streaming payload size**: Large plans may bloat SSE. Consider diff-based messages (`added`, `updated`, `removed`).
- **Frontend desync**: Ensure Plan Panel falls back to periodic GET if streaming disconnects.

## Progress Tracking
- [x] Persist plan state via controller + DTOs.
- [x] Expose dedicated plan CRUD endpoints.
- [ ] Stream live plan updates alongside chat tokens.
- [x] Integrate Plan Panel with normalised plan store + events.
- [x] Backfill unit/integration coverage + docs.

## Known Limitations & Bugs
- No open bugs logged. Add new issues to `docs/status/KnownBugs.md` and reference their IDs here.
