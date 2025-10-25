# Documentation Inventory & Freshness Audit

> **Last Updated:** October 2025  
> **Maintainer:** Documentation team

This inventory reflects the post-cleanup documentation structure. Canonical references live at the repository root and under `docs/`. Session logs, summaries, and other historical artifacts have been relocated to `docs/archive/`.

## Snapshot

- **Canonical entry points**: `README.md`, `CONTRIBUTING.md`, `START_HERE.md`, `SECURITY.md`, `DEPLOYMENT.md`, `THREATMODEL.md`.
- **Agent handoff package**: `AGENT_HANDOFF_COMPLETE.md`, `HANDOFF_SESSION_2025_10_15.md`, `HANDOFF_MYPY_FIXES_2025_10_17.md`, `HANDOFF_NEXT_PHASE.md`, `IMPLEMENTATION_CONTEXT.md`, `QUICK_START_FOR_AGENTS.md`.
- **Navigation & governance**: `docs/INDEX.md` (master index), `docs/DOCUMENTATION_GUIDE.md` (maintenance guide), and `docs/status/` (feature + bug ledgers) direct contributors to the right places.
- **Historical materials**: All October 2025 implementation notes, audits, and improvement logs live under `docs/archive/`.

## Root-Level Canonical Documents

| Path | Purpose | Status |
| --- | --- | --- |
| `README.md` | Project overview, highlights, and quick start | Authoritative |
| `START_HERE.md` | Launch instructions and troubleshooting for local setup | Authoritative |
| `CONTRIBUTING.md` | Contribution workflow, tooling, and conventions | Authoritative |
| `SECURITY.md` | Security policy and disclosure process | Authoritative |
| `DEPLOYMENT.md` | Deployment and signing guidance | Authoritative |
| `THREATMODEL.md` | Current threat model for Theoria | Authoritative |
| `AGENT_HANDOFF_COMPLETE.md` | Summary of delivered handoff materials | Active |
| `HANDOFF_SESSION_2025_10_15.md` | Session recap and deployment notes | Active |
| `HANDOFF_MYPY_FIXES_2025_10_17.md` | Strict typing follow-up summary | Active |
| `HANDOFF_NEXT_PHASE.md` | Cognitive Scholar delivery roadmap (source of truth) | Active |
| `IMPLEMENTATION_CONTEXT.md` | Architecture and implementation patterns | Active |
| `QUICK_START_FOR_AGENTS.md` | Action plan for incoming agents (Cognitive Scholar kickoff) | Active |
| `DOCUMENTATION_CLEANUP_SUMMARY.md` | Record of the October cleanup and archive reorg | Informational |
| `test-ui-enhancements.md` | Manual regression checklist for UI v2 | Reference |

## `docs/` Highlights

- **Navigation & Governance**
  - `docs/INDEX.md` — Navigation hub aligned to the new taxonomy.
  - `docs/DOCUMENTATION_GUIDE.md` — Structure, naming, and archive policy.
  - `docs/status/README.md` — Governance workflow that keeps feature docs and bug ledgers in sync.

- **AI Agents & Cognitive Scholar**
  - `QUICK_START_FOR_AGENTS.md` — Orientation packet for incoming agents.
  - `HANDOFF_NEXT_PHASE.md` — Phase-by-phase implementation guide for the Cognitive Scholar stack.
  - `docs/AGENT_AND_PROMPTING_GUIDE.md` — Prompting guardrails and gate operations documentation.

- **Architecture & Engineering**
  - `docs/BLUEPRINT.md` — System design blueprint.
  - `docs/architecture.md` / `docs/adr/` — Dependency guardrails and decisions.
  - `docs/reviews/` — Architecture and safety reviews with required follow-ups.

- **Feature Specifications**
  - `docs/CASE_BUILDER.md` — Consolidated case builder roadmap (v4 is canonical).
  - `docs/DISCOVERY_FEATURE.md` — Discovery feed specification paired with quick start.
  - `docs/FUTURE_FEATURES_ROADMAP.md` — Prioritized backlog of 25 features.

- **Operations & Runbooks**
  - `docs/SERVICE_MANAGEMENT.md` — Service orchestration and runbooks.
  - `docs/runbooks/` — Incident and escalation playbooks.
  - `docs/process/` — Execution logs, retrospectives, and postmortems awaiting archival.

- **Quality & Observability**
  - `docs/testing/TEST_MAP.md` — Comprehensive testing matrix.
  - `docs/ui-quality-gates.md` — UI acceptance thresholds.
  - `docs/dashboards/` — Quality dashboards and telemetry snapshots.

## Archive Layout (`docs/archive/`)

| Directory | Contents | Notes |
| --- | --- | --- |
| `docs/archive/2025-10/` | October 2025 feature implementation summaries (UI v2, animations, workflow improvements) | **Completed** work; kept for historical reference |
| `docs/archive/fixes/` | Bug reports and remediation summaries (e.g., ReDoS, pytest, API connection) | Point-in-time fixes |
| `docs/archive/audits/` | Audit packages, including CI/CD reviews and security analyses | Replaces legacy `audit/` root directory |
| `docs/archive/planning/` | Completed plans, including agent task breakdowns and case builder versions v1–v3 | Superseded by current specifications |
| `docs/archive/ui-sessions/` | Detailed UI refactoring and animation session logs | Superseded by the UI guidelines in `docs/` |

Archived documents are **not** maintained. When referencing historical context, prefer linking to the archive rather than reviving files at the root.

## Maintenance Guidance

- Update this inventory after major documentation reorganizations or when adding/removing canonical files.
- Keep `docs/INDEX.md`, `docs/DOCUMENTATION_GUIDE.md`, and `docs/status/FEATURE_INDEX.md` synchronized with structural changes.
- When a document becomes historical, move it to the appropriate archive subdirectory and add a note to the relevant README inside the archive.
- For roadmap and implementation status, treat `HANDOFF_NEXT_PHASE.md` as canonical and ensure downstream docs (e.g., `docs/ROADMAP.md`, `docs/DISCOVERY_FEATURE.md`) remain in sync.

## Automation

The legacy per-file tables from earlier audits have been retired. When you need a granular inventory, regenerate it on demand by combining `git ls-files '*.md'` (or `find`/`rg`) with `git log -1 --format="%cs" -- <file>` and capture the results in the relevant pull request or issue.

---

For questions about documentation maintenance, reach out in `docs/DOCUMENTATION_GUIDE.md` or open an issue with the affected paths and desired changes.
