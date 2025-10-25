# Documentation Inventory & Freshness Audit

> **Last Updated:** October 2025  
> **Maintainer:** Documentation team

This inventory reflects the post-cleanup documentation structure. Canonical references live at the repository root and under `docs/`. Session logs, summaries, and other historical artifacts have been relocated to `docs/archive/`.

## Snapshot

- **Canonical entry points**: `README.md`, `CONTRIBUTING.md`, `START_HERE.md`, `SECURITY.md`, `docs/operations/deployment-overview.md`, `THREATMODEL.md`.
- **Agent handoff package**: `AGENT_HANDOFF_COMPLETE.md`, `HANDOFF_SESSION_2025_10_15.md`, `HANDOFF_MYPY_FIXES_2025_10_17.md`, `HANDOFF_NEXT_PHASE.md`, `IMPLEMENTATION_CONTEXT.md`, `QUICK_START_FOR_AGENTS.md`.
- **Navigation aids**: `docs/meta/index.md` (master index) and `docs/meta/documentation-guide.md` (maintenance guide) are the definitive sources for researchers and contributors.
- **Historical materials**: All October 2025 implementation notes, audits, and improvement logs live under `docs/archive/`.

## Root-Level Canonical Documents

| Path | Purpose | Status |
| --- | --- | --- |
| `README.md` | Project overview, highlights, and quick start | Authoritative |
| `START_HERE.md` | Launch instructions and troubleshooting for local setup | Authoritative |
| `CONTRIBUTING.md` | Contribution workflow, tooling, and conventions | Authoritative |
| `SECURITY.md` | Security policy and disclosure process | Authoritative |
| `docs/operations/deployment-overview.md` | Deployment and signing guidance | Authoritative |
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

- **Navigation & Maintenance**
  - `docs/meta/index.md` — Comprehensive index organized by persona.
  - `docs/meta/documentation-guide.md` — Structure, naming, and archive policy.

- **Cognitive Scholar**
  - `docs/features/roadmap/roadmap.md` — MVP/Alpha/Beta milestones for hypothesis, gate, TMS, debate, and visualization layers.
  - `HANDOFF_NEXT_PHASE.md` — Phase-by-phase implementation guide for the Cognitive Scholar stack.
  - `docs/agents/prompting-guide.md` — Prompting guardrails and gate operations documentation.

- **Architecture & Operations**
  - `docs/architecture/clean-architecture.md` — System design blueprint.
  - `docs/agents/prompting-guide.md` / `docs/agents/confinement.md` — Agent framework and safety guardrails.
  - `docs/operations/service-management.md` — Service orchestration and runbooks.

- **Feature Specifications**
  - `docs/features/case-builder/overview.md` — Consolidated case builder roadmap (v4 is canonical).
  - `docs/features/roadmap/future-features-roadmap.md` — Prioritized backlog of 25 features.
  - `docs/features/ux/navigation-loading-improvements.md` — Active UI guidance that replaced the archived session logs.

- **Testing & Quality**
  - `docs/testing/TEST_MAP.md` — Comprehensive testing matrix.
  - `docs/testing/ui-quality-gates.md` — UI acceptance thresholds.
  - `docs/development/typing-standards.md` — Python and TypeScript typing policy.

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
- Keep `docs/meta/index.md` and `docs/meta/documentation-guide.md` synchronized with structural changes.
- When a document becomes historical, move it to the appropriate archive subdirectory and add a note to the relevant README inside the archive.
- For roadmap and implementation status, treat `HANDOFF_NEXT_PHASE.md` as canonical and ensure downstream docs (e.g., `docs/features/roadmap/roadmap.md`, `docs/features/discovery/overview.md`) remain in sync.

## Automation

The legacy per-file tables from earlier audits have been retired. When you need a granular inventory, regenerate it on demand by combining `git ls-files '*.md'` (or `find`/`rg`) with `git log -1 --format="%cs" -- <file>` and capture the results in the relevant pull request or issue.

---

For questions about documentation maintenance, reach out in `docs/meta/documentation-guide.md` or open an issue with the affected paths and desired changes.
