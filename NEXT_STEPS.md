# Next Steps - Cognitive Scholar Delivery

**Last Updated**: October 19, 2025  
**Current Status**: CS-001 shipped; CS-002 in flight; CS-003 backend scaffolding underway.

---

## Where We Stand

- Architecture modernization is complete (DTOs, repositories, domain errors, query tools) and covered by tests.
- Discovery pipeline runs all six engines with APScheduler feeding the Discovery Feed UI.
- Reasoning timeline UI is live; loop control scaffolding exists server-side.
- Chat workflow returns `plan` snapshots; `ResearchLoopController` persists plan state.

---

## Immediate Priorities (next 48 hours)

1. **CS-002 – Loop Controls**
   - Finalise `/chat/{session_id}/loop/control` behaviour and surface stop/step/pause states.
   - Build `LoopControls.tsx` and integrate with `ChatWorkspace.tsx`.
   - Add controller + API tests (`tests/api/test_ai_workflows_integration.py`).

2. **CS-003 – Plan API**
   - Add plan CRUD endpoints (`/chat/{session_id}/plan` GET + mutate routes) wrapping `ResearchLoopController`.
   - Stream `{"type":"plan_update"}` frames alongside chat tokens for live updates.

3. **CS-003 – Plan Panel UI**
   - Create plan store/hooks inside `theo/services/web/app/chat/`.
   - Implement `PlanPanel` component and subscribe to snapshots/streaming events.
   - Wire into `ChatWorkspace.tsx` layout adjacent to the reasoning timeline.

---

## Supporting Work

- **Testing**: Unit coverage for plan mutations, integration tests for plan routes + streaming, and Playwright/Vitest smoke for LoopControls + PlanPanel.
- **Docs**: Update `docs/tasks/TASK_005_Cognitive_Scholar_MVP_Tickets.md` and relevant handoffs as milestones land.
- **Telemetry (optional)**: Log loop control + plan events for observability.

---

## Key References

- Backend: `theo/services/api/app/ai/research_loop.py`, `theo/services/api/app/routes/ai/workflows/chat.py`, `theo/services/api/app/models/research_plan.py`.
- Frontend: `theo/services/web/app/chat/ChatWorkspace.tsx`, `theo/services/web/app/chat/hooks/useChatExecution.ts`, new Plan Panel/store modules to add.
- Tests: `tests/api/test_ai_workflows_integration.py`, `tests/api/routes/test_discoveries_v1.py`, forthcoming plan controller tests.

---

## Verification Checklist

```bash
# Loop control actions
pytest tests/api/test_ai_workflows_integration.py -k loop -v

# Plan routes (after implementation)
pytest tests/api/test_ai_workflows_integration.py -k plan -v

# Frontend smoke (after UI wiring)
npm --prefix theo/services/web run test:ui -- --grep "Plan Panel"
```

---

## Upcoming Milestones

1. **CS-004** – Argument link schema + repositories.
2. **CS-005/CS-006** – Argument map renderer + Toulmin zoom modal.
3. **CS-007/CS-008** – Truth-maintenance system and explorer UI.
4. **CS-009+** – Hypothesis runner, debate loop, belief bars, meta-prompt picker.

---

## Reminders

- Keep architecture tests (`pytest tests/architecture/ -v`) in CI to safeguard boundaries.
- Ensure new chat components support dark mode and responsive layouts.
- Document progress in `COGNITIVE_SCHOLAR_HANDOFF_NEW.md` and ticket tracker after each milestone.
- Review `docs/status/KnownBugs.md` before each planning session and update this playbook with any high-severity open issues.

Let's ship loop controls and bring the Plan Panel online! 🚀
