# Theoria - Next Phase Development Plan

> **Status:** Cognitive Scholar MVP execution underway  
> **Last Updated:** 2025-10-19  
> **Estimated Timeline:** 4-6 weeks (CS-002 -> CS-016)

---

## Executive Summary

Discovery, reasoning, dashboard, and citation foundations are live. The next phase focuses on shipping the Cognitive Scholar MVP: **loop controls**, **live plan editing**, **argument mapping with truth maintenance**, **hypothesis workflows**, and **gap->loop automation**.

### Current State
- Complete: frontend UI supports reasoning timeline, reasoning trace, and fallacy warnings in chat
- Complete: RAG workflow stable with guardrails, exports, and monitoring hooks
- Complete: discovery backend runs six engines (pattern, contradiction, gap, connection, trend, anomaly) on the APScheduler refresh cadence
- Complete: dashboard route (`dashboard.py`) and UI components surface real metrics and activity
- Complete: bibliography builder plus Zotero export cover end-to-end citation workflows
- Complete: documentation refreshed via CS-001 handoff and task tracker updates

### What's Next
1. **CS-002 to CS-004:** Deliver loop controls, live plan panel, and argument link schema
2. **CS-005 to CS-008:** Build argument map renderer, Toulmin zoom, and the truth-maintenance system
3. **CS-009 to CS-013:** Ship hypothesis management, multi-runner, debate loop, belief bars, and meta-prompt picker
4. **CS-014 to CS-016:** Integrate gap discoveries into reasoning loops with falsifier searches and retrieval budgeting

---

## Phase 1: Control Surface + Timeline (Week 1)

- CS-001 complete: timeline models (`theo/services/api/app/models/reasoning.py`) and UI (`ReasoningTimeline.tsx`) render in chat responses
- CS-002: expose stop, step, and pause endpoints plus `LoopControls.tsx`
- CS-003: render and persist plan panel edits with drag-and-drop ordering
- CS-004: finalize argument link schema in domain + persistence layers
- **Outcome:** User-steerable reasoning loop with visible state and persistence hooks

## Phase 2: Argument Maps + TMS (Week 2)

- CS-005: argument map renderer (D3) with support/contradict visualization
- CS-006: Toulmin zoom modal for grounds, warrants, qualifiers, rebuttals
- CS-007: truth-maintenance engine with justification propagation and unit tests
- CS-008: TMS explorer UI for dependency inspection and impact preview
- **Outcome:** Interactive argument visualization backed by consistent truth maintenance

## Phase 3: Hypotheses + Debates (Week 3)

- CS-009: hypothesis domain model, repository, and dashboard cards
- CS-010: multi-hypothesis runner orchestrating retrieval + scoring
- CS-011: debate loop (H1 vs H2) with LLM judge and confidence adjustments
- CS-012: belief bars showing prior→posterior deltas per evidence
- CS-013: meta-prompt picker sourced from `data/meta_prompts/procedures.yaml`
- **Outcome:** Structured hypothesis management with transparent debate outcomes

## Phase 4: Gap → Loop Integration (Week 4)

- CS-014: falsifier search operator converts gaps to targeted queries
- CS-015: retrieval budgeter enforces token/time constraints
- CS-016: wire gap discoveries into the reasoning loop and belief updates
- **Outcome:** Automated feedback cycle linking discovery gaps to reasoning loop iterations

---

## Testing Strategy

### Unit Tests
```bash
pytest tests/services/reasoning/ -v               # timeline + control DTOs
pytest tests/domain/arguments/ -v                 # Toulmin + TMS units
pytest tests/domain/hypotheses/ -v                # hypothesis models and repositories
pytest tests/services/research/ -v                # falsifier + budgeter logic
```

### Integration Tests
```bash
pytest tests/api/test_ai_workflows_integration.py -v   # loop controls + timeline payload
pytest tests/api/routes/test_discoveries_v1.py -v      # discovery pipeline health
pytest tests/api/test_dashboard_route.py -v            # dashboard metrics
pytest tests/api/test_citation_exports.py -v           # bibliography + Zotero
```

### Manual Testing
- [ ] Interrupt a chat run via stop/step controls and verify timeline updates
- [ ] Reorder plan panel items and confirm backend execution order changes
- [ ] Inspect argument map for a multi-claim response; validate Toulmin zoom details
- [ ] Run multi-hypothesis workflow and observe debate resolution + belief bars
- [ ] Trigger gap discovery -> falsifier search loop; ensure budgeter applies limits

---

## Deployment Checklist

1. Install dependencies: `pip install -r requirements.txt`
2. Apply migrations for new reasoning and hypothesis tables when introduced
3. Restart services: `.\start-theoria.ps1`
4. Verify APScheduler logs include discovery cycle completions
5. Smoke test: chat session with timeline, dashboard metrics, Zotero export

---

## Success Metrics

- **Phase 1:** >=90% of chat sessions display timeline + controls without errors
- **Phase 2:** Users create >=1 argument map per session; TMS resolves contradictions within 2 seconds
- **Phase 3:** 2-4 hypotheses per question with debate confidence deltas logged
- **Phase 4:** 60% of identified gaps trigger falsifier searches; retrieval budget overruns <5%

---

## Risk Mitigation

- **Loop control latency?** Optimize workflow cancellation hooks and add tracing
- **Argument map complexity?** Start with capped node counts; add clustering for large graphs
- **TMS performance?** Cache justification evaluations and instrument for cycle detection
- **Retrieval overrun?** Pre-calculate cost envelopes and short-circuit expensive branches

---

## Quick Reference

- `theo/services/api/app/models/reasoning.py` - timeline + control DTOs
- `theo/services/api/app/routes/ai/workflows/chat.py` - workflow payload updates
- `theo/services/web/app/components/ReasoningTimeline.tsx` - chat reasoning UI
- `docs/tasks/TASK_005_Cognitive_Scholar_MVP_Tickets.md` - ticket breakdown (CS-001 -> CS-016)
- `COGNITIVE_SCHOLAR_HANDOFF.md` - active handoff context and status ledger
- `docs/status/FEATURE_INDEX.md` - documentation ownership index
- `docs/status/KnownBugs.md` - live bug ledger

---

## Next Session Start Here
1. Confirm CS-001 completion in the task tracker (done ✅)
2. Implement loop control endpoints and UI (CS-002)
3. Add plan panel scaffolding with mock data (CS-003)
4. Define argument link schema across domain + repository (CS-004)
5. Draft TMS design update ahead of Phase 2 kickoff

---

**Ready to ship the Cognitive Scholar MVP!**

## Known Limitations & Bugs
- Track open issues in `docs/status/KnownBugs.md`; reference IDs here when applicable. Currently no active blockers recorded.
4. **CS-014 to CS-016:** Integrate gap discoveries into reasoning loops with falsifier searches and retrieval budgeting
