# Documentation Index

> **Last Updated:** 2025-10-26

This index highlights the current source-of-truth documents for Theoria. Anything marked as legacy now lives in `docs/archive/2025-10-26_core/` with an archive banner.

## Quick Navigation

- **Getting Started**
  - [README.md](../README.md) — Project overview, setup, and onboarding.
  - [START_HERE.md](../START_HERE.md) — PowerShell launcher walkthrough.
  - [CONTRIBUTING.md](../CONTRIBUTING.md) — Contribution workflow and tooling expectations.

- **Architecture & Operations**
  - [architecture.md](architecture.md) - High-level platform architecture.
  - [INTEGRATIONS.md](INTEGRATIONS.md) - External system and deployment integration guidance.
  - [Repo-Health.md](Repo-Health.md) - Signals and scorecard for repository maintenance.
  - [runbooks/database_initialization.md](runbooks/database_initialization.md) - Database bootstrapping steps and required performance indexes.

- **API & Agent Surface**
  - [API.md](API.md) — REST surface area and integration requirements.
  - [theoria_instruction_prompt.md](theoria_instruction_prompt.md) — System prompt contract for AI agents interfacing with Theoria.
  - [AGENT_CONFINEMENT.md](AGENT_CONFINEMENT.md) — Guardrails for agent execution and sandboxing.

- **User Research & Strategy**
  - [research/adjacent_user_needs.md](research/adjacent_user_needs.md) — Adjacent user pain points and opportunity backlog for product planning.

- **Testing & Quality**
  - [testing.md](testing.md) — Current testing posture and coverage heatmap.
  - [testing/TEST_MAP.md](testing/TEST_MAP.md) — Authoritative testing matrix and ownership.
  - [coverage/90_PERCENT_STRATEGY.md](coverage/90_PERCENT_STRATEGY.md) — Active strategy to achieve 90% coverage for critical packages.
  - [coverage/COVERAGE_SNAPSHOT_2025-10-31.md](coverage/COVERAGE_SNAPSHOT_2025-10-31.md) — Latest quantitative snapshot of line coverage and priority gaps.
  - [tests/utils/query_profiler.py](../tests/utils/query_profiler.py) — Profiling helper referenced in QA tasks.

- **Documentation Utilities**
  - [document_inventory.md](document_inventory.md) — Live manifest of active documentation.
  - `docs/adr/` — Architectural Decision Records (authoritative; unchanged).

## Legacy Archives

- **2025-10-26 Core Archive:** [`docs/archive/2025-10-26_core/`](archive/2025-10-26_core/) contains superseded specifications, roadmaps, and reference guides. Each file starts with an archive banner noting the date.
- **Older Collections:** Existing archives remain under [`docs/archive/`](archive/). When reviving a document, remove the banner, move it back under `docs/`, and refresh references here.

> Need to archive something new? Follow the workflow in [README.md](../README.md#documentation-archival-workflow) to keep the index tidy for the next agent.
