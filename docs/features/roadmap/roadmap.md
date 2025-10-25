# Roadmap

> **Source of truth:** `HANDOFF_NEXT_PHASE.md` (last updated 2025-02-10)

The Cognitive Scholar initiative reshapes Theoria's planning lens. This roadmap surfaces the delivery checkpoints for the
Hypothesis & Debate stack. Refer to `HANDOFF_NEXT_PHASE.md` for detailed task breakdowns, owners, and acceptance criteria.

## Current Status

- **Hypothesis Objects** – Data contract drafted; API scaffolding pending.
- **Cognitive Gate** – Prompt kernel prototypes exist in notebooks; no production service yet.
- **POU Loop** – Existing Prompt-Observe-Update loop still uses legacy evaluator and needs to be swapped for the gate-aware
  controller.
- **Thought Management System (TMS)** – No persisted thread manager yet; relies on flat trail logs.
- **Debate Loop** – Debate primitives exist in research prompts but lack orchestration and guardrails.
- **Visualization Layers** – Lightweight hypothesis table shipped; timeline and graph overlays remain in design.

## MVP (Weeks 1–3): Cognitive Scholar Foundations

- **Hypothesis Objects v1**
  - Define persistent hypothesis schema and migrations.
  - Ship CRUD APIs and SDK helpers for research sessions.
  - Surface hypotheses in `/research/hypotheses` with status, confidence, and supporting evidence counts.
- **Cognitive Gate v0**
  - Promote the gate kernel into a FastAPI service module.
  - Wire the gate into the Prompt-Observe-Update (POU) loop for chat and research flows.
  - Implement gate telemetry: entry scores, rejection reasons, timing.
- **POU Loop Swap**
  - Replace the legacy evaluator in `GuardedAnswerPipeline` with gate-driven control decisions.
  - Update regression trails to exercise pass/block branches.
  - Document fail-open/fail-closed policies for moderators.

## Alpha (Weeks 4–6): Managed Reasoning & Disputation

- **Thought Management System (TMS) v0**
  - Introduce TMS service responsible for hypothesis selection, branching, and archival.
  - Add per-step metadata (prompts, decisions, verdicts) with retention policies.
  - Provide admin tools to inspect and replay TMS sessions.
- **Debate Loop v0**
  - Stand up pro/con agent pair orchestrated by the Cognitive Gate.
  - Persist debate rounds as structured artifacts linked to hypotheses.
  - Add guardrails and scoring rubric for moderator decisions.
- **Visualization Layer v1**
  - Render debate timelines and hypothesis evolution graphs in `/research/hypotheses`.
  - Add gate telemetry dashboards summarizing admission, rejection, and override rates.

## Beta (Weeks 7–9): Research UX Polish & Prompt Governance

- **Meta-Prompt Picker**
  - Curate prompt presets aligned with research goals (Exploratory, Apologetic, Critical, Synthesis).
  - Provide UI affordances to swap presets mid-session with guardrail warnings.
  - Track usage analytics and feedback loops for preset tuning.
- **Advanced Visualization Layer**
  - Introduce heatmaps for contention points and stacked confidence trendlines.
  - Export hypothesis/debate trails as shareable reports (PDF/Markdown).
- **TMS & Debate Hardening**
  - Load-test multi-hypothesis sessions, capture performance baselines.
  - Expand safety suite covering adversarial prompts, hallucination checks, and citation drift.
  - Prepare Beta feedback rubric and incorporate participant onboarding checklist.

## Maintenance Notes

- Keep this summary synchronized with `HANDOFF_NEXT_PHASE.md` after each milestone.
- Update dependent documentation (`docs/agents/prompting-guide.md`, `docs/meta/document-inventory.md`) whenever milestone names or
  scopes change.
