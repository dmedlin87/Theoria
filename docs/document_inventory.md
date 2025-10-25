# Documentation Inventory & Freshness Audit

> **Last Updated:** October 2025  
> **Maintainer:** Documentation team

This inventory reflects the post-cleanup documentation structure. Canonical references live at the repository root and under `docs/`. Session logs, summaries, and other historical artifacts have been relocated to `docs/archive/`.

## Snapshot

- **Canonical entry points**: `README.md`, `CONTRIBUTING.md`, `START_HERE.md`, `SECURITY.md`, `DEPLOYMENT.md`, `THREATMODEL.md`, `QUICK_START_AGENTS.md`, `AGENT_CONTEXT.md`, `CHANGELOG.md`.
- **Agent handoff archive**: Completed packages (e.g., Cognitive Scholar CS-001) now live under `docs/archive/handoffs/` alongside `IMPLEMENTATION_CONTEXT.md` references when historical context is required.
- **Navigation aids**: `docs/INDEX.md` (master index) and `docs/DOCUMENTATION_GUIDE.md` (maintenance guide) are the definitive sources for researchers and contributors.
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
| `QUICK_START_AGENTS.md` | Orientation and environment setup for incoming agents | Authoritative |
| `AGENT_CONTEXT.md` | Living architecture and workflow context for agents | Authoritative |
| `CHANGELOG.md` | Recent repository history and documentation log | Authoritative |
| `IMPLEMENTATION_CONTEXT.md` | Deep-dive architecture references sourced from prior handoffs | Reference |
| `DOCUMENTATION_CLEANUP_SUMMARY.md` | Record of the October cleanup and archive reorg | Informational |
| `test-ui-enhancements.md` | Manual regression checklist for UI v2 | Reference |

## `docs/` Highlights

- **Navigation & Maintenance**
  - `docs/INDEX.md` — Comprehensive index organized by persona.
  - `docs/DOCUMENTATION_GUIDE.md` — Structure, naming, and archive policy.

- **Cognitive Scholar**
  - `docs/ROADMAP.md` — MVP/Alpha/Beta milestones for hypothesis, gate, TMS, debate, and visualization layers.
  - `HANDOFF_NEXT_PHASE.md` — Phase-by-phase implementation guide for the Cognitive Scholar stack.
  - `docs/AGENT_AND_PROMPTING_GUIDE.md` — Prompting guardrails and gate operations documentation.

- **Architecture & Operations**
  - `docs/BLUEPRINT.md` — System design blueprint.
  - `docs/AGENT_AND_PROMPTING_GUIDE.md` / `docs/AGENT_CONFINEMENT.md` — Agent framework and safety guardrails.
  - `docs/SERVICE_MANAGEMENT.md` — Service orchestration and runbooks.

- **Feature Specifications**
  - `docs/CASE_BUILDER.md` — Consolidated case builder roadmap (v4 is canonical).
  - `docs/FUTURE_FEATURES_ROADMAP.md` — Prioritized backlog of 25 features.
  - `docs/UI_NAVIGATION_LOADING_IMPROVEMENTS.md` — Active UI guidance that replaced the archived session logs.

- **Testing & Quality**
  - `docs/testing/TEST_MAP.md` — Comprehensive testing matrix.
  - `docs/ui-quality-gates.md` — UI acceptance thresholds.
  - `docs/typing-standards.md` — Python and TypeScript typing policy.

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
- Keep `docs/INDEX.md` and `docs/DOCUMENTATION_GUIDE.md` synchronized with structural changes.
- When a document becomes historical, move it to the appropriate archive subdirectory and add a note to the relevant README inside the archive.
- For roadmap and implementation status, treat `HANDOFF_NEXT_PHASE.md` as canonical and ensure downstream docs (e.g., `docs/ROADMAP.md`, `docs/DISCOVERY_FEATURE.md`) remain in sync.

## Automation

The legacy per-file tables from earlier audits have been retired. When you need a granular inventory, regenerate it on demand by combining `git ls-files '*.md'` (or `find`/`rg`) with `git log -1 --format="%cs" -- <file>` and capture the results in the relevant pull request or issue.

---

For questions about documentation maintenance, reach out in `docs/DOCUMENTATION_GUIDE.md` or open an issue with the affected paths and desired changes.
