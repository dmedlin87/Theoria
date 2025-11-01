# Theoria Evidence Cards

## Primary vs Secondary Evidence

- **Primary evidence** captures direct, unaltered artefacts that substantiate a claim (e.g., transcript segments, commentary excerpts, dataset snapshots). These should come from canonical tooling that already enforces provenance such as the Claim Card detail view in the audit dashboard, which exposes attachments and verification metrics alongside every escalation.【F:docs/runbooks/high_risk_claim_escalation.md†L16-L34】
- **Secondary evidence** summarises or contextualises primary sources (analyst synthesis, cross-source comparisons, or model-generated interpretations). When adding secondary notes, retain links to the originating primary artefacts and record any assumptions, consistent with the documentation inventory policy that prioritises authoritative entry points and traceability across `docs/` references.【F:docs/document_inventory.md†L1-L37】

## OSIS Normalization Policy

- Extract scripture references with the shared detection pipeline and normalise each match to canonical OSIS strings using `pythonbible` before persisting them on passages or evidence payloads.【F:docs/archive/2025-10-26_core/OSIS.md†L1-L23】
- When evidence cards reference scripture, prefer the same OSIS fields exposed by the public API (`osis` query parameters and anchors) so downstream consumers can reuse retrieval and aggregation endpoints without bespoke parsing.【F:docs/API.md†L207-L418】
- Preserve inclusive ranges (`Book.Chapter.Verse-Book.Chapter.Verse`) and deduplicate overlapping spans before storage to avoid conflicting verse keys within the same card.【F:docs/archive/2025-10-26_core/OSIS.md†L17-L23】

## Stability Rubric

- **Stable** – Evidence card aligns with current guardrails: supporting tests are green, documentation links are up to date, and no outstanding dependency or architecture risks are flagged against the relevant surface area in the repository health report.【F:docs/Repo-Health.md†L1-L66】
- **Watch** – Card depends on modules or workflows undergoing active stabilisation (e.g., regression-suite hardening, fixture refactors, or import-boundary work). Track the remediation steps outlined in the stabilisation plan and re-evaluate once the success criteria are met.【F:docs/archive/2025-10-26_core/codebase_stabilization_plan.md†L1-L48】【F:docs/archive/2025-10-26_core/codebase_stabilization_plan.md†L56-L64】
- **At Risk** – Card references brittle or flaky systems (failed regression gates, unresolved CVEs, or breached import rules). Escalate through the audit workflow and capture remediation evidence per the escalation runbook so the instability is visible and triaged.【F:docs/Repo-Health.md†L14-L63】【F:docs/runbooks/high_risk_claim_escalation.md†L1-L41】

## Commit Hygiene Guidance

- Follow the contributing guide: keep temporary diagnostics out of version control, regenerate constraint lockfiles after dependency edits, and align test evidence with the published test map whenever cards require code changes.【F:CONTRIBUTING.md†L1-L74】
- Group related updates into focused commits with clear messaging so repository health signals remain actionable; reference relevant docs (e.g., this guide, the test map, or API contracts) to aid reviewers scanning the documentation inventory.【F:docs/document_inventory.md†L1-L43】
