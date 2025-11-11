# Theoria

<p align="center">
  <em>Your theological research, unified and verse-anchored.</em>
</p>

Stop losing citations in scattered notes and unreliable AI summaries. Theoria transforms your research library into a searchable, verse-aware knowledge graph where every automated insight traces back to canonical text. Index your sources, normalize Scripture references, and retrieve evidence with AI assistance you can trust.

## Table of Contents
1. [Why Theoria](#why-theoria)
2. [Core Capabilities](#core-capabilities)
3. [System Requirements](#system-requirements)
4. [Real-World Workflows](#real-world-workflows)
5. [Quick Start](#quick-start)
6. [Architecture Overview](#architecture-overview)
7. [Local Development](#local-development)
8. [Common Issues](#common-issues)
9. [Documentation Map](#documentation-map)
10. [Support & Contribution](#support--contribution)

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
| Integrations | REST API + CLI automation hooks for automation and orchestration |

Additional feature deep-dives live in [`docs/archive/`](docs/archive/). Current initiatives and planning notes are captured in [`docs/INDEX.md`](docs/INDEX.md) and [`docs/planning/SIMPLIFICATION_PLAN.md`](docs/planning/SIMPLIFICATION_PLAN.md).

---

## System Requirements

| Resource | Minimum | Recommended | Notes |
| --- | --- | --- | --- |
| RAM | 8 GB | 16 GB | ML-powered enrichment and embedding jobs benefit from additional memory. |
| Storage | 2 GB | Depends on corpus | Allocate extra space for audio/video ingestion pipelines and cached embeddings. |
| CPU | 4 cores | 8+ cores | Parallel ingestion and evaluation suites scale with available cores. |
| OS | macOS, Linux, Windows (WSL2) |  | Verified on macOS Sonoma, Ubuntu 22.04, and Windows 11 with WSL2. |

GPU acceleration is optional. When available, configure the ML extras (see [`docs/INDEX.md`](docs/INDEX.md) for the latest ML guidance) for accelerated embedding generation.

---

## Real-World Workflows

- 📖 **Sermon Preparation**: Search “faith works James” to surface James 2:14–26 plus relevant excerpts from your personal library.
- 🔍 **Comparative Studies**: Query “trinity early church” to retrieve patristic sources with normalized verse cross references.
- ✍️ **Academic Writing**: Export structured citations suitable for papers and dissertations straight from the evidence panel.
- 🧭 **Research Synthesis**: Combine deterministic retrieval with curated LLM prompts while preserving traceability to canonical text.

---

## Quick Start

> **Prerequisites:** Python 3.11+, Node.js 20+, and a running PostgreSQL instance (local or remote). The CLI scripts will provision a development database automatically when none is specified. Installing [go-task](https://taskfile.dev/) is encouraged but not required—raw shell equivalents are noted for every critical step.

### Phase 1: Environment Setup

1. **Clone & prepare environment**
   ```bash
   git clone https://github.com/dmedlin87/theoria.git
   cd theoria
   python -m venv .venv && source .venv/bin/activate
   pip install ".[api]" -c constraints/prod.txt
   pip install ".[ml]" -c constraints/prod.txt
   pip install ".[dev]" -c constraints/dev.txt

Regenerate these lockfiles after changing dependency ranges with:

```bash
python scripts/update_constraints.py
```

To ensure the repository constraints are up to date during CI or reviews, run the script with `--check` to validate without rewriting the files.

The production constraint set also pins a CPU-only PyTorch wheel by embedding the appropriate `--index-url`/`--extra-index-url` directives so builds avoid GPU-only Triton conflicts.
   ```

2. **Provision frontend tooling**
   ```bash
   cd theo/services/web
   npm install
   cd -
   ```

3. **Configure authentication** (choose one)
   ```bash
   # API key-based auth (recommended)
   export THEO_API_KEYS='["local-dev-key"]'

   # or temporarily allow unauthenticated requests (development only)
   export THEO_ALLOW_INSECURE_STARTUP=1
   export THEO_AUTH_ALLOW_ANONYMOUS=1
   ```
   Additional authentication strategies (OIDC, session-based, API tokens) are documented in [`SECURITY.md`](SECURITY.md) and highlighted through [`docs/INDEX.md`](docs/INDEX.md).

   > **Production / staging:** Always configure API keys or JWT credentials. The
   > API exits during startup if anonymous access remains enabled when the
   > runtime environment is anything other than development/testing. Set
   > `THEO_LOCAL_INSECURE_OVERRIDES=0` when you want local scripts to exercise
   > the same production guards.

### Phase 2: Launch Services

4. **Launch background services**
   ```bash
   task db:start  # optional helper; defaults to local dockerized postgres
   ```
   The repository uses [go-task](https://taskfile.dev/) for orchestration. If you prefer raw commands or do not have `task` installed, set `DATABASE_URL` and start PostgreSQL manually—for example:
   ```bash
   docker run --rm --name theoria-db -e POSTGRES_PASSWORD=theoria -e POSTGRES_USER=theoria -e POSTGRES_DB=theoria \
     -p 5432:5432 postgres:16
   export DATABASE_URL="postgresql://theoria:theoria@127.0.0.1:5432/theoria"
   ```

5. **Launch API**
   ```bash
   uvicorn theo.infrastructure.api.app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   Visit the interactive docs at <http://localhost:8000/docs>.

6. **Launch Web UI**
   ```bash
   cd theo/services/web
   export NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
   export THEO_SEARCH_API_KEY="Bearer local-dev-key"  # remove "Bearer" to send via X-API-Key header
   npm run dev
   ```
   Open <http://localhost:3000> and press ⌘K/CTRL+K to explore the command palette.

### Phase 3: Explore (Optional)

7. **Seed demo content**
   ```bash
   ./scripts/reset_reseed_smoke.py --log-level INFO
   ```
   The command loads a small corpus of sample sermons, research snippets, and evaluation datasets for experimentation.

---

## Architecture Overview

```
┌──────────────┐      ┌───────────────────────┐      ┌─────────────────────┐
│ Ingestion    │──►──│ Retrieval Services     │──►──│ UI & Integrations   │
│ (CLI & API)  │      │ (FastAPI + Workers)    │      │ (Next.js, REST/CLI) │
└──────────────┘      └───────────────────────┘      └─────────────────────┘
        ▲                       │                         │
        │                       ▼                         ▼
  Documents & Media     Verse-normalized store      Research & authoring
```

- **API & Workers**: `theo/infrastructure/api` (FastAPI, background jobs, pgvector).
- **Web Experience**: `theo/services/web` (Next.js, Radix UI toolkit, theme system).
- **Docs & Playbooks**: `docs/` (architecture, workflows, policies).
- **Automation Scripts**: `scripts/` (dev orchestration, reseeding, evaluation).
- **Quality Gates**: `tests/` (unit, integration, ranking, UI smoke suites).

For detailed architecture patterns, see [`docs/architecture.md`](docs/architecture.md) for service boundaries, data flow, and scaling considerations. The [Architecture Overview](README_ARCHITECTURE_UPDATES.md) file captures ongoing platform investments at a glance, and additional ADRs live under [`docs/adr/`](docs/adr/).

---

## Local Development

### One command dev loop
- **PowerShell**: `./scripts/dev.ps1`
- **Bash**: `./scripts/run.sh`

Both scripts boot the API and Next.js app, wiring ports and environment variables automatically. REST and CLI integrations are supported through the primary API stack—see [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) for examples and recommended workflows.

Install the orchestration tooling with `brew install go-task/tap/go-task`, `scoop install task`, or download binaries from the [go-task releases](https://github.com/go-task/task/releases). All commands listed in this README include raw equivalents when Task is optional.

### Dependency management
- Python extras live in `pyproject.toml` (`base`, `api`, `ml`, `dev`) with corresponding lockfiles under `constraints/`.
- Install extras with `pip install .[api] -c constraints/prod.txt` plus `[ml]`/`[dev]` when ML features or tooling are required.
- Run `task deps:lock` after editing dependency definitions to regenerate the pinned constraints via `pip-compile`.

### Testing & quality gates
- **Python tests (fast)**: `task test:fast` or `pytest -m "not (slow or gpu or contract)"`
- **Full Python suite**: `task test:full` or `pytest --schema --pgvector --contract`
- **Regression & slow prerequisites**: [`docs/testing.md`](docs/testing.md)
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

Stop with `docker compose down`.

### Deployment options

For staging and production scenarios-including container images, Fly.io, and bare-metal strategies-consult [`DEPLOYMENT.md`](DEPLOYMENT.md) and the infrastructure manifests under [`infra/`](infra/). Observability, scaling, and backup recommendations live in [`docs/Repo-Health.md`](docs/Repo-Health.md).

---

## Common Issues

- **PostgreSQL connection errors**: Ensure port 5432 is available or override `DATABASE_URL` to target your preferred instance.
- **Node.js version conflicts**: Verify `node --version` returns 20.x or higher; use `nvm use` from `theo/services/web/.nvmrc` if installed.
- **Missing Task runner**: Either install go-task (see above) or run the equivalent shell commands provided alongside each task.
- **ML model downloads failing**: Confirm internet access and disk space, then rerun `pip install .[ml] -c constraints/prod.txt` or follow the offline cache instructions referenced in [`docs/INDEX.md`](docs/INDEX.md).

---

## Documentation Map

| Category | Start Here |
| --- | --- |
| Architecture | [`docs/architecture.md`](docs/architecture.md) |
| API & Agents | [`docs/API.md`](docs/API.md), [`docs/theoria_instruction_prompt.md`](docs/theoria_instruction_prompt.md), [`docs/AGENT_CONFINEMENT.md`](docs/AGENT_CONFINEMENT.md) |
| User Research | [`docs/research/adjacent_user_needs.md`](docs/research/adjacent_user_needs.md) |
| Operations | [`docs/Repo-Health.md`](docs/Repo-Health.md) |
| Documentation Index | [`docs/document_inventory.md`](docs/document_inventory.md), [`docs/INDEX.md`](docs/INDEX.md) |
| Testing & Quality | [`docs/testing.md`](docs/testing.md), [`docs/testing/TEST_MAP.md`](docs/testing/TEST_MAP.md) |
| Legacy Archive | [`docs/archive/2025-10-26_core/`](docs/archive/2025-10-26_core/), [`docs/archive/`](docs/archive/) |

Use [`docs/INDEX.md`](docs/INDEX.md) as the master directory of all documentation.

### Documentation Archival Workflow

- **When to archive:** Any reference doc that is superseded or dormant for a full release cycle should move under `docs/archive/<YYYY-MM-DD>_<context>/`.
- **How to archive:** Create the dated folder, prepend the file with an archive banner (Markdown: `> **Archived on YYYY-MM-DD**`, text: `# Archived on YYYY-MM-DD`, JSON: `// Archived on YYYY-MM-DD`), and move the file into the new folder.
- **Binary assets:** Move the asset and add a sibling note (e.g., `*.archive-note.md`) that records the archive date and reason.
- **Index updates:** Remove archived docs from the table above and from `docs/INDEX.md`, then add a brief pointer to the new archive folder so other agents can still discover the material.

---

## Support & Contribution

- Review [CONTRIBUTING.md](CONTRIBUTING.md) for branching, testing, and review expectations.
- Security questions? Consult [SECURITY.md](SECURITY.md) and the threat model in [`THREATMODEL.md`](THREATMODEL.md).
- Join the discussion via issues and pull requests—feature proposals with verse-anchored acceptance criteria are especially welcome.

---

**License**: Refer to the repository for license information.
