# Theoria - Next Phase Development Plan

> **Status:** Ready for implementation
> **Last Updated:** 2025-02-10
> **Estimated Timeline:** 6–8 weeks

---

## Executive Summary

The next delivery window advances the **Cognitive Scholar** initiative: durable hypothesis objects, gate-managed reasoning, and
structured debate workflows. The plan is organized around successive capability layers—gate, loop control, thought management,
debate orchestration, and prompt governance. Each phase concludes with demos and telemetry hooks to keep research UX and safety
in lockstep.

### Current State ✅
- ✅ Frontend scaffolding for `/research/hypotheses`
- ✅ Prompt kernel prototypes for the Cognitive Gate
- ✅ Baseline Prompt-Observe-Update loop in production
- ✅ Reasoning telemetry primitives (trails, fallacy reports)
- ✅ Documentation and safety guardrails for agents

### What's Next 🎯
1. Productionize Cognitive Gate v0 and ship hypothesis objects.
2. Swap the Prompt-Observe-Update loop to be gate-aware and log all outcomes.
3. Launch Thought Management System (TMS) v0 with persistence and admin tooling.
4. Orchestrate Debate Loop v0 and wire structured visualizations.
5. Deliver Meta-Prompt picker and finalize Beta readiness hardening.

---

## Phase 1 (Week 1–2): Hypothesis Objects & Cognitive Gate v0

### Goals
- Persist research hypotheses with lifecycle metadata and evidence hooks.
- Stand up the Cognitive Gate service for admission control and policy enforcement.

### Tasks
- **Hypothesis Schema & Storage**
  - Create migrations for `hypotheses`, `hypothesis_evidence`, and linking tables.
  - Implement repository/service layer APIs for CRUD and status transitions.
  - Backfill tests covering optimistic concurrency and soft-deletes.
- **Cognitive Gate Service v0**
  - Convert the prompt kernel into `theo/services/api/app/ai/gate/service.py`.
  - Implement score computation, policy thresholds, and audit logging.
  - Expose `/api/ai/gate/evaluate` endpoint with contract tests.
- **Integration & Telemetry**
  - Wire gate decisions into research/chat flows in `GuardedAnswerPipeline`.
  - Emit structured telemetry (scores, policy, overrides) to metrics stream.
  - Document gate operations, fail-open criteria, and override workflow in `docs/AGENT_AND_PROMPTING_GUIDE.md`.

## Phase 2 (Week 3): POU Loop Swap & Research UI Refresh

### Goals
- Replace legacy evaluator with gate-managed control logic.
- Expose hypotheses and gate results in the research UI.

### Tasks
- **POU Loop Swap**
  - Update `GuardedAnswerPipeline` to delegate to the Cognitive Gate.
  - Add fallback handling for gate errors (retry, degrade, operator alert).
  - Expand unit and integration tests to cover pass, reject, and override paths.
- **UI & API Updates**
  - Enhance `/research/hypotheses` page to display gate verdicts, scores, and timestamps.
  - Extend research API responses with hypothesis IDs and gate metadata.
  - Update docs and demos illustrating hypothesis creation and review flows.

## Phase 3 (Weeks 4–5): Thought Management System (TMS) v0

### Goals
- Manage concurrent hypotheses, branching, and archival through a dedicated service.
- Provide operators with tooling to inspect and replay thought sequences.

### Tasks
- **TMS Service Layer**
  - Implement `theo/services/api/app/ai/tms/service.py` with session lifecycle management.
  - Persist step history including prompt, agent, gate verdict, and outcome.
  - Create retention policy jobs for pruning inactive sessions.
- **Admin & Observability**
  - Build admin UI for TMS inspection (filter by hypothesis, gate verdict, outcome).
  - Add replay endpoint to re-run or audit sessions under new policies.
  - Instrument metrics for session duration, branch counts, and overrides.

## Phase 4 (Weeks 6): Debate Loop v0 & Visualization Layer v1

### Goals
- Introduce orchestrated pro/con agents moderated by the Cognitive Gate.
- Visualize debates and hypothesis evolution in the research UI.

### Tasks
- **Debate Orchestration**
  - Implement debate coordinator managing rounds, agent roles, and gate validations.
  - Persist debate transcripts linked to hypotheses and TMS sessions.
  - Establish safety guardrails, scoring rubric, and escalation paths for moderator intervention.
- **Visualization Layer v1**
  - Add timeline and graph components showing hypothesis confidence changes.
  - Surface gate/debate telemetry dashboards (admission rate, overrides, contention points).
  - Capture UX feedback checklist post-demo for iteration planning.

## Phase 5 (Week 7–8): Meta-Prompt Picker & Beta Hardening

### Goals
- Allow researchers to select prompt presets aligned with their objectives.
- Harden the system for limited Beta release with telemetry, safety, and documentation updates.

### Tasks
- **Meta-Prompt Picker**
  - Curate presets (Exploratory, Apologetic, Critical, Synthesis) with guardrail annotations.
  - Add UI controls to switch presets mid-session with validation warnings.
  - Track preset usage, satisfaction scores, and gate outcomes per preset.
- **Beta Hardening**
  - Run load tests for multi-hypothesis debate sessions; capture baseline metrics.
  - Expand adversarial test suite covering hallucination, citation drift, and prompt abuse.
  - Update onboarding documentation, create Beta feedback rubric, and finalize release checklist.

---

## Testing Strategy

### Unit Tests
```bash
pytest tests/domain/hypotheses/ -v
pytest tests/api/ai/test_gate.py -v
pytest tests/api/ai/test_pou_loop.py -v
pytest tests/api/ai/test_tms.py -v
pytest tests/api/ai/test_debate.py -v
```

### Integration & E2E
```bash
pytest tests/api/test_research_workflow.py -v
pytest tests/ui/test_hypothesis_workflow.py -v
npm run test:e2e:research --workspace theo/services/web
```

### Telemetry & Safety Checks
```bash
python scripts/telemetry/validate_gate_events.py
pytest tests/safety/test_prompt_guardrails.py -v
```

---

## Dependencies & Risks

- **Model Variance** – Gate scoring depends on frontier models; capture calibration curves per provider.
- **Telemetry Overhead** – New metrics streams may impact ingestion; batch writes and monitor latency.
- **Operator Training** – Gate overrides and debate moderation require updated runbooks and demos.

---

## Communication Plan

- Weekly demo cadence showcasing gate decisions, TMS session replays, and debate transcripts.
- Async updates in `#theoria-research` summarizing gate metrics, hypothesis counts, and debate outcomes.
- Mid-cycle retrospective after Phase 3 to adjust scope for Beta hardening.

