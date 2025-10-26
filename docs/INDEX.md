# Documentation Index

> **Last Updated:** 2025-10-26

This index highlights the current source-of-truth documents for Theoria. Anything marked as legacy now lives in `docs/archive/2025-10-26_core/` with an archive banner.

## Quick Navigation

- **Getting Started**
  - [README.md](../README.md) — Project overview, setup, and onboarding.
  - [START_HERE.md](../START_HERE.md) — PowerShell launcher walkthrough.
  - [CONTRIBUTING.md](../CONTRIBUTING.md) — Contribution workflow and tooling expectations.

- **Architecture & Operations**
  - [architecture.md](architecture.md) — High-level platform architecture.
  - [architecture_review.md](architecture_review.md) — Latest architecture assessment and follow-up work.
  - [codebase_stabilization_plan.md](codebase_stabilization_plan.md) — Live resilience and hardening plan.
  - [Repo-Health.md](Repo-Health.md) — Signals and scorecard for repository maintenance.
  - [runbooks/database_initialization.md](runbooks/database_initialization.md) — Database bootstrapping steps and required performance indexes.

- **API & Agent Surface**
  - [API.md](API.md) — REST surface area and integration requirements.
  - [theoria_instruction_prompt.md](theoria_instruction_prompt.md) — System prompt contract for AI agents interfacing with Theoria.
  - [AGENT_CONFINEMENT.md](AGENT_CONFINEMENT.md) — Guardrails for agent execution and sandboxing.

- **Testing & Quality**
  - [testing.md](testing.md) — Current testing posture and coverage heatmap.
  - [testing/TEST_MAP.md](testing/TEST_MAP.md) — Authoritative testing matrix and ownership.
  - [tests/utils/query_profiler.py](../tests/utils/query_profiler.py) — Profiling helper referenced in QA tasks.

- **Documentation Utilities**
  - [document_inventory.md](document_inventory.md) — Live manifest of active documentation.
  - `docs/adr/` — Architectural Decision Records (authoritative; unchanged).

## Legacy Archives

- **2025-10-26 Core Archive:** [`docs/archive/2025-10-26_core/`](archive/2025-10-26_core/) contains superseded specifications, roadmaps, and reference guides. Each file starts with an archive banner noting the date.
- **Older Collections:** Existing archives remain under [`docs/archive/`](archive/). When reviving a document, remove the banner, move it back under `docs/`, and refresh references here.

> Need to archive something new? Follow the workflow in [README.md](../README.md#documentation-archival-workflow) to keep the index tidy for the next agent.
