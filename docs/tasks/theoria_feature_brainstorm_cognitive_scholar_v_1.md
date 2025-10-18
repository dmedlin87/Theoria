# Theoria Feature Brainstorm — Cognitive Scholar V1

> **Goal**: Turn Theoria into an autonomous, context‑aware “super‑scholar” that forms, tests, and refines theories with transparent reasoning—while remaining steerable by the user.
>
> **Status**: Consolidated spec with addendum and appendix.  
> **Last updated**: 2025‑10‑18

---

## 0) Feature Map & Phasing

**Phases**
- **MVP (2–4 weeks)**: Core hypothesis objects; Detective→Critic loop; Reasoning Timeline; basic Hypothesis Dashboard; stop/step controls; Contradiction Finder v0; Citation Verifier v0; perspective toggle; depth slider.
- **Alpha (4–8 weeks)**: Truth‑Maintenance Graph; Toulmin mapper; multi‑hypothesis parallel runs; Debate Mode (self‑debate); Insight Detector + Panel; Knowledge‑Gap Generator; constitution‑guided self‑critique; source credibility scoring.
- **Beta (8–16 weeks)**: Bayesian updater visualization; causal graph builder; multi‑agent panel (skeptic/apologist/neutral); retrieval budgeter; research plan view; argument Venn diagrams; longitudinal memory; evaluation suite + rubrics; plugin toolchain.

**Buckets**: Autonomy; Steerability; Visualization; Memory/Knowledge; Quality/Evaluation; Tooling; Integrations; DevEx.

---

## 1) Core Objects & Data Contracts

### 1.1 Hypothesis Object
- **Fields**: `id`, `question_id`, `thesis`, `priors` (0–1), `confidence` (posterior), `status` (proposed/tested/refuted/supported), `supporting_evidence[]`, `counter_evidence[]`, `assumptions[]`, `notes`, `created_at`.
- **Why**: Enables multi‑track answers and belief updates.

### 1.2 Evidence Object
- **Fields**: `id`, `source_id`, `quote/span`, `osis_range?`, `claim_ref?`, `stance` (pro/con/neutral), `credibility_score`, `explanation`.
- **Why**: Atomic, citation‑first units that fuel argument graphs.

### 1.3 Argument Link (Toulmin)
- **Fields**: `claim_id`, `grounds[] (evidence_ids)`, `warrant`, `backing`, `qualifier`, `rebuttals[]`.
- **Why**: Enforces scholarly structure; directly renderable.

### 1.4 Belief / Truth‑Maintenance Graph (TMG)
- **Nodes**: Hypotheses, claims, evidence, assumptions.  
- **Edges**: `supports`, `contradicts`, `depends_on`.  
- **Ops**: Retract/update cascade when an upstream node changes.

---

## 2) Autonomy Features

### 2.1 Detective→Critic Loop (Auto‑Mode, MVP)
- **What**: Initial answer via Detective prompt; internal Critic reviews; auto‑revise until `confidence ≥ threshold` or `max_loops` reached.
- **Controls**: Depth slider (0–3); stop/step.
- **Why**: Quality boost with minimal prompting.

### 2.2 Multi‑Hypothesis Runner
- **What**: Generate 2–4 hypotheses, run retrieval and scoring per hypothesis in parallel, present ranked outcomes.
- **Why**: Avoids premature convergence.

### 2.3 Knowledge‑Gap Generator
- **What**: After a pass, produce “missing‑evidence” queries; auto‑search within budget.
- **Why**: Curiosity by default.

### 2.4 Contradiction Finder v0
- **What**: Scan current evidence for explicit conflicts (e.g., contradiction seeds, lexical negations, timeline clashes).
- **Why**: Falsifiability built‑in.

### 2.5 Constitution‑Guided Self‑Critique
- **What**: Codify scholarly principles (logic, multi‑view, citation honesty, clarity); run 1–2 self‑checks against them; revise.
- **Why**: Consistent guardrails without human nudge.

### 2.6 Retrieval Budgeter
- **What**: Soft caps per loop (max docs, tokens, time); summarize/merge to stay within budget.
- **Why**: Predictable latency and cost.

---

## 3) Steerability & Control Plane

### 3.1 Live Plan Panel
- **What**: Miniature plan of the current loop (steps, queued queries, tools to call).
- **Actions**: Pause/step/skip; reprioritize steps; edit a query inline.

### 3.2 Depth & Mode Toggles
- **Modes**: Brief | Standard | Deep‑Dive | Autonomous Research.  
- **Depth**: Affects loop count, breadth, and debate on/off.

### 3.3 Perspective Routing
- **What**: User chooses lenses (skeptic/neutral/apologist/custom); orchestrator fans out and later synthesizes.

### 3.4 Rails
- **Constraints**: Allowed sources, time windows, stance hints, safety filters.

---

## 4) Visualization Layer

### 4.1 Reasoning Timeline (MVP)
- **Steps**: Understand → Gather → Tensions → Draft → Critique → Revise → Synthesize.  
- **UX**: Collapsible; each step shows citations used; jump‑to‑edit.

### 4.2 Hypothesis Dashboard (MVP)
- **Cards**: Thesis; confidence bar; key supports/contradictions; open questions.

### 4.3 Argument Mapper (Toulmin)
- **View**: Claim center with grounds/backing/qualifier; hover shows source.  
- **Export**: PDF/PNG.

### 4.4 Perspective Venn / Compare Table
- **Show**: Consensus vs. unique claims; per‑lens deltas.

### 4.5 Bayesian Belief Update Plot (Alpha)
- **Show**: Prior→posterior bars per hypothesis; per‑evidence deltas.

### 4.6 Causal Graph Builder (Beta)
- **Use**: Doctrinal/rhetorical causality; arrows with strength annotations.

### 4.7 Insights Panel
- **Feed**: Novelty, rare cross‑references, surprising co‑occurrences; save to notebook.

---

## 5) Memory, Knowledge & Provenance

### 5.1 Semantic Memory Graph
- **What**: Persistent entities, themes, scholars, recurring claims; edges weighted over time.  
- **Use**: Context prefetch; analogical retrieval.

### 5.2 Source Credibility Model
- **Signals**: Publication type, recency, peer review, author reputation, cross‑agreement → output 0–1 score.

### 5.3 Provenance Ledger
- **Track**: Every claim→evidence path; source versions; retractions; diff view when sources update.

### 5.4 Longitudinal Learning
- **What**: Store refuted patterns, successful prompt variants, frequent fallacies caught; feed meta‑optimizer.

---

## 6) Quality & Evaluation

### 6.1 Metrics
- **Coherence**: % fallacy‑free steps.  
- **Grounding**: % claims with valid citations.  
- **Breadth**: Distinct perspectives used.  
- **Rigor**: Contradictions surfaced per 1k words.  
- **Latency/Cost**: Per mode, per loop.

### 6.2 Benchmarks
- **Internal sets**: Curated theology/textual‑criticism questions with gold rationales; debate tasks; contradiction hunts.

### 6.3 Rubrics & Checklists
- **Critic rubric**: Evidence sufficiency; counter‑evidence handled; clarity; logic; humility (hedging when needed).

---

## 7) Tooling & Services

### 7.1 Logic Checker Microservice
- **API**: `/logic/check` → fallacy types; contradiction flags; argument skeleton extraction.

### 7.2 Citation Verifier
- **API**: `/cite/verify` → retrieve source text windows; match support spans; score alignment.

### 7.3 Timeline Builder
- **API**: `/chronology/suggest` → event extraction; date normalization; conflict detection.

### 7.4 OSIS/Scripture Normalizer (extend existing)
- **Add**: Pericope alignment; cross‑tradition mapping; commentary hooks.

### 7.5 Debate Orchestrator
- **API**: `/debate/run` with roles, topic, constraints → transcript + verdict + best‑points list.

---

## 8) Integrations

- **Ingest**: PDFs (labels/SDS), YouTube transcripts, web, Markdown notes (front matter for provenance).  
- **External tools**: Theorem/proof checker (where relevant), calculators, translators.  
- **Export**: Markdown dossiers; printable argument maps; shareable hypothesis cards.

---

## 9) Developer Experience (DevEx)

- **Prompt Registry**: Versioned meta‑prompts with A/B tests; rollback.  
- **Tracing**: Per‑step logs with tool calls; redaction‑safe for sharing.  
- **Sandbox**: Replay a research session deterministically with seeds.

---

## 10) UX Sketches (Text)

1) **Top Bar**: Mode selector + depth slider + Stop/Step.  
2) **Left Pane**: Reasoning Timeline (expandable steps).  
3) **Center**: Current answer with inline citations; insight chips.  
4) **Right Pane Tabs**: Hypotheses | Argument Map | Perspectives | Plan | Notebook.

---

## 11) Prompts (Summaries)

- **Detective**: Clarify → enumerate hypotheses → collect evidence per hypothesis → note tensions → draft.  
- **Critic**: Attack logic; demand counter‑evidence; grade clarity/hedging; list fixes.  
- **Revise**: Apply fixes; improve warrants; add qualifiers; surface open questions.  
- **Debate**: Role A vs. Role B → timed rounds → judge summary.  
- **Constitution**: Check against scholarly principles; generate violations; repair.

---

## 12) Example Flows

**Flow A (MVP)**: User asks → Detective draft → Critic flags 2 issues → auto‑retrieve 2 sources → revise → hypothesis card + timeline exposed.

**Flow B (Alpha)**: Same, plus multi‑hypothesis: two cards with 0.68 vs. 0.27 posterior; Venn shows consensus points; user clicks rebuttal, triggering another loop.

---

## 13) Quick Wins (Next 2 Weeks)

1) Ship Reasoning Timeline + stop/step.  
2) Implement Hypothesis object + dashboard rendering.  
3) Wire simple Critic prompt; single auto‑revise pass.  
4) Contradiction Finder v0: lexical negation + seed list.  
5) Citation Verifier v0: fetch + fuzzy‑match spans.

---

## 14) Risks & Mitigations

- **Loop drift**: Add budgets + user interrupt; show plan.  
- **Over‑automation**: Default to transparent view; easy mode switch.  
- **Latency**: Summarize aggressively; cache partial results; parallel hypothesis runs.  
- **Hallucination**: Verifier gate; constitution penalties; require source spans.

---

## 15) Success Criteria

- Users report higher trust (traceable reasoning) and fewer follow‑ups.  
- Measured drop in ungrounded claims; rise in contradictions surfaced and resolved.  
- Stable latency bands per mode; predictable costs.

---

*End V1 — ready to iterate.*

---

## Addendum — Updates from “Adaptive Scholar” Report (2025‑10‑18)

**Summary**: The report sharpens the architecture around a **Cognitive Gearbox** (System‑1 ↔ System‑2), a falsifier‑first **Predict→Observe→Update (POU)** loop, a tripartite logic engine with **TMS**, debate as a built‑in red team, constitutional virtues, and hierarchical memory. Below are concrete deltas applied to this brainstorm.

### A) Architecture Deltas
- **Cognitive Gearbox (PRIME‑style gating)**  
  New services: `quickthink-s1` (fast abductive draft) and `deepreason-s2` (deliberative pipeline).  
  **Reflection Gate**: Trigger S2 when any of: high entropy/low log‑prob margin; citation coverage < threshold; contradiction ratio > 0; novelty flag hit; or user requests deep mode.  
  **Telemetry**: Record gate causes for later tuning.
- **POU Loop (Predict→Observe→Update)**  
  Replace linear Detective flow with **Hypothesize → Predict → Target‑Falsifiers → Test → Update**.  
  Add a **Falsifier Search Operator** that prioritizes anomaly/exception queries per hypothesis.
- **Tripartite Logic Engine**  
  Abduction (S1 hypothesis generator); Deduction (derive testable predictions); **Defeasible/TMS** (belief revision).  
  Minimal **TMS v0**: Store justifications; on contradiction, cascade‑retract dependent claims.
- **Internal Debate Module**  
  Spawn H1 vs. H2 (or Pro vs. Con) with timed rounds; produce transcript + judged verdict.  
  Expose **Debate Trace** in UI; feed verdict back into hypothesis ranking.
- **Constitutional Epistemics**  
  Draft a **Scholar’s Constitution** (honesty, humility, falsifiability, clarity). Use as a self‑critique checklist pre‑answer.
- **Hierarchical Memory (HSGM‑style)**  
  Global summary graph of topics/scholars/claims; local segment graphs per document.  
  **Context Router**: Hit global graph → zoom into locals → hydrate working set.

### B) Visualization Deltas
- **Multi‑Layer Explainability**  
  Default **Argument Map** (macro) → click to **Toulmin Zoom** (meso) → optional **Bayesian/Causal Board** (micro).  
  **TMS Dependency Explorer**: Visualize which claims/evidence will retract on a premise change.  
  **Belief Update Bars**: Prior→posterior per hypothesis after each evidence batch.

### C) Steerability Deltas
- **Meta‑Prompt Library (Director/Actor)**: User selects procedures (Scientific Method v1.2, Historical‑Critical, Literature Review, Debate‑First, etc.).  
- **Guard‑Railed Autonomy**: Constitution + active meta‑prompt define rails; within them, the agent runs autonomously.  
- **Direct TMS Edits**: Advanced users can assert/retract premises; system shows an impact preview.

### D) Metrics & Evaluation
- **Falsifier Hit Rate**: % of searches that return disconfirming evidence.  
- **Gate Effectiveness**: % of S2 invocations that materially change the answer.  
- **Debate Win Margin**: Judge confidence that the winner’s position is better‑supported.  
- **Calibration**: Brier/ACE between stated confidence and eventual verdicts.

### E) Roadmap Adjustments
- **MVP (next 2–4 weeks)**: Cognitive Gate v0 (entropy + citation coverage); POU flow swap; TMS v0; Debate v0 (single round); Argument Map + Toulmin Zoom; Meta‑Prompt picker.  
- **Alpha (4–8 weeks)**: Bayesian belief bars; Hierarchical Memory Router; constitution check pass; multi‑round debate with judge; TMS Explorer.  
- **Beta (8–16 weeks)**: Causal board; direct TMS editing UI; credibility model integration; evaluation dashboard with calibration.

### F) New Tickets (snapshot)
1. **Gate v0**: Compute entropy/log‑prob margin; add citation‑coverage metric; wire S2 trigger.  
2. **Falsifier Operator**: Query templates for anomalies/exceptions; route to retrieval.  
3. **TMS v0**: Data model for justifications; contradiction cascade; API for preview.  
4. **Debate v0**: Roles; one rebuttal round; simple LLM judge; store transcript.  
5. **Meta‑Prompt Picker UI**: Mode switcher + procedure descriptions.  
6. **Argument Map → Toulmin Zoom**: Backend JSON schema + front‑end renderer.  
7. **Belief Bars v1**: Compute prior/posterior deltas per hypothesis.

> These updates are now reflected in the feature brainstorm and should be used for ticketing and implementation planning.

---

## Appendix — Codex Review Synthesis & Execution Order (2025‑10‑18)

**Why this appendix**: Four Codex agents reviewed a pre‑addendum draft. Their feedback largely validates direction and sharpens priorities. This appendix folds that signal into an execution plan and acceptance checks without altering core scope.

### A) Execution Order (influenced by Codex feedback)
1. **Control Surface + Timeline (MVP)**: Ship stop/step, depth slider, and live plan panel together with the Reasoning Timeline so users can steer loops in real time.  
2. **Argument Mapping + Toulmin Zoom (MVP)**: Implement Argument Link schema (claim/grounds/warrant/backing/qualifier/rebuttal) and a renderer; add hover spans and basic credibility badges.  
3. **TMS v0 + Auto‑Retractions (MVP)**: Minimal truth‑maintenance with justification links and cascade retraction on contradiction; expose a preview before applying retract.  
4. **Two‑Track H1/H2 + Debate v0 (MVP+)**: Run H1 vs. H2 in parallel, one rebuttal round, simple judge; feed verdict into hypothesis ranking.  
5. **Belief Bars v1 (MVP+, pulled forward)**: Show prior→posterior deltas per hypothesis after each evidence batch.  
6. **Gap→Loop Plumbing (MVP+)**: Convert Discoveries/Gap signals into falsifier‑targeted follow‑up queries injected into the current loop within retrieval budgets.

### B) Definition of Done — Acceptance Checks
- **Cascade**: Editing/retracting an assumption triggers TMS cascade; dependent conclusions auto‑retract; event log records impact.  
- **Argument UI**: Every claim node renders Toulmin fields; hovering a ground shows the exact support span and its credibility badge.  
- **Debate**: Parallel H1/H2 run stores a transcript; judge verdict adjusts confidence by ≥ configurable threshold; verdict rationale is viewable.  
- **Steerability**: Plan panel lists queued queries/tools; **Step** advances one tool call; **Stop** halts and returns current synthesis.  
- **Belief Bars**: Prior/posterior bars update after each batch; calibration metrics logged per answer.  
- **Gap Loop**: When a gap signal fires, a new falsifier‑oriented query is appended and executed, respecting retrieval budgets.

### C) Ticket Additions (beyond §F)
8. **Credibility v0**: Rule‑based scoring (venue type, recency, peer‑review flag, cross‑agreement) → `evidence.credibility_score` with badges; expose in Argument Map and Hypothesis cards.  
9. **Gap→Loop Wiring**: API/UX to ingest Discoveries gap signals and auto‑generate follow‑up queries; budget controls + audit log.

### D) Roadmap Tweaks
- Move **Belief Bars v1** from Alpha to **MVP+** (minimal visualization; full calibration dashboard remains Beta).  
- Keep **Argument Map + Toulmin Zoom** in MVP (unlocks explainability early).

> Use this appendix for sprint planning; it reflects Codex feedback without changing the addendum’s architecture.

