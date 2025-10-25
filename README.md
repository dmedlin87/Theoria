# Theoria

<p align="center">
  <em>Deterministic research engine for theology.</em>
</p>

Index your sources, normalize Scripture references, and retrieve verse-anchored evidence with AI assistance you can trust. Theoria keeps citations primary and models secondary so that every automated summary, paraphrase, or comparison is traceable back to the canon text that informed it.

## Table of Contents
1. [Why Theoria](#why-theoria)
2. [Core Capabilities](#core-capabilities)
3. [System Overview](#system-overview)
4. [Quick Start](#quick-start)
5. [Local Development](#local-development)
6. [Documentation Map](#documentation-map)
7. [Support & Contribution](#support--contribution)

---

## Why Theoria

Theoria unifies your theological research library—papers, notes, transcripts, and audio—into a single verse-aware knowledge graph. Every result is anchored to normalized OSIS references, so citations remain verifiable whether you are preparing sermons, running comparative studies, or drafting devotionals.

**What you can expect:**
- **Grounded answers** backed by deterministic retrieval with citations for every verse.
- **Productivity workflows** that combine AI summarization with strict reference enforcement.
- **Operational confidence** with observability, testing, and performance guardrails baked in.

> "Theoria keeps our exegetical work anchored to the text, even when we move fast." — Early access user

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

Additional feature deep-dives live in [`docs/archive/`](docs/archive/). The public roadmap and current areas of focus are tracked in [`NEXT_STEPS.md`](NEXT_STEPS.md).

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

For architecture detail, start with [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) and the ADR directory under [`docs/adr/`](docs/adr/). The [Architecture Overview](README_ARCHITECTURE_UPDATES.md) file captures ongoing platform investments at a glance.

---

## Quick Start

> **Prerequisites:** Python 3.11+, Node.js 20+, and a running PostgreSQL instance (local or remote). The CLI scripts will provision a development database automatically when none is specified.

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

4. **Launch background services**
   ```bash
   task db:start  # optional helper; defaults to local dockerized postgres
   ```

5. **Launch API**
   ```bash
   uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   Visit the interactive docs at <http://localhost:8000/docs>.

6. **Launch Web UI**
   ```bash
   cd theo/services/web
   export NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
   export THEO_SEARCH_API_KEY="Bearer local-dev-key"  # remove "Bearer" to send via X-API-Key
   npm run dev
   ```
   Open <http://localhost:3000> and press ⌘K/CTRL+K to explore the command palette.

7. **Seed demo content (optional)**
   ```bash
   ./scripts/reset_reseed_smoke.py --log-level INFO
   ```
   The command loads a small corpus of sample sermons, research snippets, and evaluation datasets for experimentation.

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

Override database URLs or API keys through the script flags when targeting Postgres or remote services. The scripts are idempotent and safe to run repeatedly as you iterate on ingestion pipelines.

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

| Category | Start Here |
| --- | --- |
| Architecture & Decisions | [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md), [`docs/adr/`](docs/adr/) |
| APIs & Integration | [`docs/API.md`](docs/API.md), [`docs/mcp_integration_guide.md`](docs/mcp_integration_guide.md), [`docs/authentication.md`](docs/authentication.md) |
| CLI & Automation | [`docs/CLI.md`](docs/CLI.md), [`theo/services/cli`](theo/services/cli) |
| UI & UX | [`docs/archive/2025-10/`](docs/archive/2025-10/), [`theo/services/web/app/components/ui`](theo/services/web/app/components/ui) |
| Testing & Quality | [`docs/testing/TEST_MAP.md`](docs/testing/TEST_MAP.md), [`docs/performance.md`](docs/performance.md), [`SECURITY.md`](SECURITY.md) |
| Roadmaps & Case Builder | [`docs/CASE_BUILDER.md`](docs/CASE_BUILDER.md), [`docs/archive/2025-10/UI_OVERHAUL_SUMMARY.md`](docs/archive/2025-10/UI_OVERHAUL_SUMMARY.md) |

Use [`docs/INDEX.md`](docs/INDEX.md) as the master directory of all documentation.

---

## Support & Contribution

- Review [CONTRIBUTING.md](CONTRIBUTING.md) for branching, testing, and review expectations.
- Security questions? Consult [SECURITY.md](SECURITY.md) and the threat model in [`THREATMODEL.md`](THREATMODEL.md).
- Join the discussion via issues and pull requests—feature proposals with verse-anchored acceptance criteria are especially welcome.

---

**License**: Refer to the repository for license information.
