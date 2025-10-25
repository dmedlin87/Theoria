# Theoria

> **Deterministic research engine for theology.** Index your sources, normalize Scripture references, and retrieve verse-anchored evidence with AI assistance you can trust.

## Table of Contents
1. [Why Theoria](#why-theoria)
2. [Core Capabilities](#core-capabilities)
3. [System Overview](#system-overview)
4. [Quick Start](#quick-start)
5. [For AI Agents](#for-ai-agents)
6. [Local Development](#local-development)
7. [Documentation Map](#documentation-map)
8. [Support & Contribution](#support--contribution)

---

## Why Theoria

Theoria unifies your theological research library—papers, notes, transcripts, and audio—into a single verse-aware knowledge graph. Every result is anchored to normalized OSIS references, so citations remain verifiable whether you are preparing sermons, running comparative studies, or drafting devotionals.

**What you can expect:**
- **Grounded answers** backed by deterministic retrieval with citations for every verse.
- **Productivity workflows** that combine AI summarization with strict reference enforcement.
- **Operational confidence** with observability, testing, and performance guardrails baked in.

---

## Core Capabilities

| Area | Highlights |
| --- | --- |
| Retrieval | Hybrid semantic + lexical search, pgvector embeddings, deterministic verse aggregation |
| Scripture | Automatic OSIS normalization, verse span aggregation, cross-translation linking |
| Ingestion | Local files, URLs, YouTube, bulk CLI pipelines with citation preservation |
| Workflows | Sermon prep, comparative analysis, topic monitoring, export tooling (Markdown/NDJSON/CSV) |
| Experience | Modern Next.js UI, command palette (⌘K/CTRL+K), dark mode, WCAG 2.1 AA accessibility |
| Integrations | Model Context Protocol (MCP) server, API + CLI automation hooks |

Additional feature deep-dives live in [`docs/archive/`](docs/archive/).

---

## System Overview

```
┌──────────────┐      ┌───────────────────────┐      ┌────────────────┐
│ Ingestion    │──►──│ Retrieval Services     │──►──│ UI & MCP Tools │
│ (CLI & API)  │      │ (FastAPI + Workers)    │      │ (Next.js, MCP) │
└──────────────┘      └───────────────────────┘      └────────────────┘
        ▲                       │                         │
        │                       ▼                         ▼
  Documents & Media     Verse-normalized store      Research & authoring
```

- **API & Workers**: `theo/services/api` (FastAPI, background jobs, pgvector).
- **Web Experience**: `theo/services/web` (Next.js, Radix UI toolkit, theme system).
- **Docs & Playbooks**: `docs/` (architecture, workflows, policies).
- **Automation Scripts**: `scripts/` (dev orchestration, reseeding, evaluation).
- **Quality Gates**: `tests/` (unit, integration, ranking, MCP, UI smoke suites).

For architecture detail, start with [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) and the ADR directory under [`docs/adr/`](docs/adr/).

---

## Quick Start

1. **Clone & prepare environment**
   ```bash
   git clone https://github.com/.../theoria.git
   cd theoria
   python -m venv .venv && source .venv/bin/activate
   pip install ".[api]" -c constraints/api.txt
   pip install ".[ml]" -c constraints/ml.txt
   pip install ".[dev]" -c constraints/dev.txt
   ```

2. **Provision frontend tooling**
   ```bash
   cd theo/services/web
   npm install
   cd -
   ```

3. **Configure authentication** (choose one)
   ```bash
   export THEO_API_KEYS='["local-dev-key"]'
   # or
   export THEO_AUTH_ALLOW_ANONYMOUS=1  # development only
   ```

4. **Launch API**
   ```bash
   uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   Visit the interactive docs at <http://localhost:8000/docs>.

5. **Launch Web UI**
   ```bash
   cd theo/services/web
   export NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
   export THEO_SEARCH_API_KEY="Bearer local-dev-key"  # remove "Bearer" to send via X-API-Key
   npm run dev
   ```
   Open <http://localhost:3000> and press ⌘K/CTRL+K to explore the command palette.

---

## For AI Agents

Incoming agents can jump straight into the maintained handoff package:

- **Orientation**: [`QUICK_START_FOR_AGENTS.md`](QUICK_START_FOR_AGENTS.md) provides the mission briefing, tech stack cheatsheet, and day-one checklist.
- **Delivery context**: [`AGENT_HANDOFF_COMPLETE.md`](AGENT_HANDOFF_COMPLETE.md) links every artifact that shipped with the Cognitive Scholar engagement.
- **Active scope**: [`HANDOFF_NEXT_PHASE.md`](HANDOFF_NEXT_PHASE.md) and [`NEXT_STEPS.md`](NEXT_STEPS.md) describe the phased roadmap, acceptance criteria, and open threads.
- **Background reading**: [`IMPLEMENTATION_CONTEXT.md`](IMPLEMENTATION_CONTEXT.md) captures architecture constraints, and [`COGNITIVE_SCHOLAR_HANDOFF_NEW.md`](COGNITIVE_SCHOLAR_HANDOFF_NEW.md) summarizes domain decisions.

Pair this packet with the [Documentation Map](#documentation-map) to locate deep dives, runbooks, and historical context.

---

## Local Development

### One command dev loop
- **PowerShell**: `./scripts/dev.ps1`
- **Bash**: `./scripts/run.sh`

Both scripts boot the API and Next.js app, wiring ports and environment variables automatically. Pass `-IncludeMcp` or `-McpPort` to enable the MCP server alongside the stack.

### Dependency management
- Python extras live in `pyproject.toml` (`base`, `api`, `ml`, `dev`) with corresponding lockfiles under `constraints/`.
- Install extras with `pip install .[api] -c constraints/api.txt` plus `[ml]`/`[dev]` when ML features or tooling are required.
- Run `task deps:lock` after editing dependency definitions to regenerate the pinned constraints via `pip-compile`.

### Testing & quality gates
- **Python tests (fast)**: `task test:fast` or `pytest -m "not (slow or gpu or contract)"`
- **Full Python suite**: `task test:full` or `pytest --schema --pgvector --contract`
- **Web tests**: from `theo/services/web`, run `npm test` or `npm run test:vitest`
- **Playwright smoke**: `npm run test:e2e:smoke`
- **Performance baselines**: Lighthouse CI policy lives in [`docs/performance.md`](docs/performance.md)

### Database seeding
- Unix/macOS: `./scripts/reset_reseed_smoke.py --log-level DEBUG`
- PowerShell: `./scripts/reset-reseed-smoke.ps1 -LogLevel DEBUG`

Override database URLs or API keys through the script flags when targeting Postgres or remote services.

### Docker Compose
```bash
cd infra
docker compose up --build -d
```
- Web: <http://localhost:3000>
- API: <http://localhost:8000/docs>
- MCP: `docker compose up mcp`

Stop with `docker compose down`.

---

## Documentation Map

| Need | Where to Look |
| --- | --- |
| **Project entry points** | [`docs/INDEX.md`](docs/INDEX.md) for navigation, [`START_HERE.md`](START_HERE.md) for local launch, [`README.md`](README.md) for the product story |
| **AI agent briefings** | [`QUICK_START_FOR_AGENTS.md`](QUICK_START_FOR_AGENTS.md), [`AGENT_HANDOFF_COMPLETE.md`](AGENT_HANDOFF_COMPLETE.md), [`HANDOFF_NEXT_PHASE.md`](HANDOFF_NEXT_PHASE.md) |
| **Product & roadmap** | [`docs/ROADMAP.md`](docs/ROADMAP.md), [`docs/status/`](docs/status/) indexes, [`docs/tasks/`](docs/tasks/) planning artifacts |
| **Architecture & engineering** | [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md), [`docs/architecture.md`](docs/architecture.md), [`docs/adr/`](docs/adr/), [`docs/reviews/`](docs/reviews/) |
| **APIs & integrations** | [`docs/API.md`](docs/API.md), [`docs/CLI.md`](docs/CLI.md), [`docs/authentication.md`](docs/authentication.md), [`docs/mcp_integration_guide.md`](docs/mcp_integration_guide.md) |
| **Operations & runbooks** | [`docs/SERVICE_MANAGEMENT.md`](docs/SERVICE_MANAGEMENT.md), [`docs/runbooks/`](docs/runbooks/), [`docs/process/`](docs/process/) |
| **Quality & observability** | [`docs/testing/`](docs/testing/), [`docs/ui-quality-gates.md`](docs/ui-quality-gates.md), [`docs/dashboards/`](docs/dashboards/), [`dashboard/`](dashboard/) snapshots |
| **Security & risk** | [`SECURITY.md`](SECURITY.md), [`docs/security/`](docs/security/), [`docs/AGENT_CONFINEMENT.md`](docs/AGENT_CONFINEMENT.md), [`docs/redteam.md`](docs/redteam.md) |
| **Historical context** | [`docs/archive/`](docs/archive/) for superseded plans, audits, and UI session logs |

Use the [Documentation Guide](docs/DOCUMENTATION_GUIDE.md) for maintenance policy and curation tips.

---

## Support & Contribution

- Review [CONTRIBUTING.md](CONTRIBUTING.md) for branching, testing, and review expectations.
- Security questions? Consult [SECURITY.md](SECURITY.md) and the threat model in [`THREATMODEL.md`](THREATMODEL.md).
- Join the discussion via issues and pull requests—feature proposals with verse-anchored acceptance criteria are especially welcome.

---

**License**: Refer to the repository for license information.
