# Agent Context & Current Architecture

[⬅️ Back to the README](README.md)

This document distills the essential architecture, conventions, and active surfaces compiled from the legacy agent handoff packages, [`IMPLEMENTATION_CONTEXT.md`](IMPLEMENTATION_CONTEXT.md), and the current repository layout. Treat it as the living context file that complements the product overview in the README.

---

## Platform Snapshot
- **Product mission** – Theoria delivers deterministic, verse-anchored theological research workflows with hybrid retrieval, agent assistance, and UI automation. (See the "Why Theoria" and "Core Capabilities" sections in the [README](README.md).)
- **Primary stacks** – FastAPI workers and background jobs (`theo/infrastructure/api`), Next.js app router frontend (`theo/services/web`), PostgreSQL with `pgvector`, and CLI automation tooling.
- **Operational guardrails** – Scripts under `scripts/` orchestrate dev loops, while `task` targets and `pytest` suites enforce regression safety. Refer to [`CONTRIBUTING.md`](CONTRIBUTING.md) for expectations.

## Architecture Highlights
- **Hexagonal layering** – Domain logic in `theo/domain` stays pure and framework-free; application facades in `theo/application` orchestrate persistence; adapters integrate external systems; services expose APIs and UI. [`IMPLEMENTATION_CONTEXT.md`](IMPLEMENTATION_CONTEXT.md) contains diagrams and code templates for ports/adapters.
- **Discovery engines** – Engines share the `dataclass` + `.detect()` contract and are registered in `theo/infrastructure/api/app/discoveries/service.py`. Follow the sample patterns in [`IMPLEMENTATION_CONTEXT.md`](IMPLEMENTATION_CONTEXT.md#architecture-patterns) when adding new discovery types.
- **Agent & prompting guardrails** – Safety patterns and operational limits live in [`docs/AGENT_AND_PROMPTING_GUIDE.md`](docs/AGENT_AND_PROMPTING_GUIDE.md) and [`docs/AGENT_CONFINEMENT.md`](docs/AGENT_CONFINEMENT.md); align new reasoning flows with those constraints.

## Development Workflow
1. **Bootstrap tooling** with the launcher in [`START_HERE.md`](START_HERE.md) or manually via the Quick Start commands in the [README](README.md#quick-start).
2. **Run targeted tests** (`task test:fast`, `pytest -m "not slow"`) before iterating on discovery engines or API changes; see [`docs/testing/TEST_MAP.md`](docs/testing/TEST_MAP.md) for full coverage expectations.
3. **Observe type standards** in both Python (`mypy.ini`, `typing-standards.md`) and TypeScript (`theo/services/web` uses strict TypeScript and CSS modules).
4. **Document changes** by updating [`CHANGELOG.md`](CHANGELOG.md) and the archive directories when you complete a handoff or retire docs.

## Current Priorities
- **Stabilize contradiction seed migrations, harden ingest error handling, and repair router inflight deduplication.** The concrete tasks and references are tracked in [`docs/next_steps_plan.md`](docs/next_steps_plan.md).
- **Maintain documentation hygiene.** Any new handoff or summary should land under `docs/archive/handoffs/` while the canonical entry points stay in the repository root. Update [`docs/document_inventory.md`](docs/document_inventory.md) after every reorganization.

## Where to Dive Deeper
- [`docs/INDEX.md`](docs/INDEX.md) – Global navigation by persona and domain area.
- [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) – System blueprint with sequence diagrams and service maps.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) & [`HANDOFF_NEXT_PHASE.md`](docs/archive/handoffs/HANDOFF_NEXT_PHASE.md) – Strategic and tactical planning for Cognitive Scholar follow-ups.
- [`docs/DOCUMENTATION_GUIDE.md`](docs/DOCUMENTATION_GUIDE.md) – Standards for naming, archiving, and maintaining documentation.

---

Return to the [README](README.md) whenever you need the canonical elevator pitch or onboarding map. This context file focuses on the technical surface area so you can move from orientation to execution without re-reading every archived handoff.
