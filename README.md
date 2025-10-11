# Theo Engine

**A research engine for theology** that indexes your library (papers, notes, YouTube transcripts, audio), normalizes Scripture references (OSIS), and provides deterministic, verse-anchored search with a Verse Aggregator across your entire corpus.

See [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) for the complete system architecture.

## Features

### Core Capabilities

- **Document Ingestion** – Ingest local files, URLs, and YouTube content with automatic parsing, chunking, and citation preservation
- **Scripture Normalization** – Detect and normalize Bible references to OSIS format (e.g., `John.1.1`)
- **Hybrid Search** – Combine pgvector embeddings with lexical search for optimal retrieval
- **Verse Aggregator** – View every snippet across your corpus for any OSIS reference, with jump links to original sources
- **Bulk CLI** – Walk folders of source files and submit them to the API or worker pipeline

### Generative AI Workflows

Theo Engine layers grounded generative capabilities on top of the deterministic retrieval core:

- **Multi-Provider Support** – Securely store credentials for OpenAI, Anthropic, Azure, and local adapters; register custom model presets via the admin API
- **Verse-Linked Research** – Run sermon prep, comparative analysis, multimedia insight extraction, devotional guides, and collaboration flows with strict OSIS-anchored citations
- **Export Deliverables** – Generate Markdown, NDJSON, and CSV exports for sermons, lessons, and Q&A transcripts with reproducibility manifests
- **Topic Monitoring** – Track emerging theological topics via OpenAlex-enhanced clustering with weekly digest notifications
- **Real-Time Tracking** – Monitor background ingestion jobs, edit document metadata inline, and surface historian notes in the web UI

### Getting Started

- **CLI Usage**: Run `python -m theo.services.cli.ingest_folder --help` or see the [CLI guide](docs/CLI.md)
- **MCP Integration**: Follow the [MCP integration execution guide](docs/mcp_integration_guide.md) for ChatGPT connector setup

## Quick Start

### Repository layout

The codebase is split into a handful of top-level packages to keep the
retrieval pipeline, web application, and developer tooling isolated:

- `theo/services/api` &mdash; FastAPI service, background workers, and
  ingestion pipeline primitives
- `theo/services/web` &mdash; Next.js frontend that consumes the search and
  ingestion APIs
- `docs/` &mdash; Product plans, runbooks, architecture notes, and task
  backlogs referenced throughout the project
- `scripts/` &mdash; Helper utilities for training, reseeding fixtures, and
  coordinating local development workflows
- `tests/` &mdash; Unit and integration suites covering ingestion, ranking,
  and MCP connectors

Refer to these directories while reading the quick start steps below so you
can map each command to the relevant subsystem.

### Prerequisites

```bash
pip install -r requirements.txt
```

### Running Tests

Execute the automated test suite from the repository root:

```bash
pytest
```

### Running the API

Start the FastAPI service (SQLite default):

```bash
uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation available at <http://localhost:8000/docs>

### Running the Web UI

The Next.js application lives under `theo/services/web`:

```powershell
cd theo\services\web
$Env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
$Env:THEO_SEARCH_API_KEY = "Bearer <search-api-token>"  # omit "Bearer" to send via X-API-Key
npm install   # first time only
npm run dev
```

Open <http://localhost:3000> in your browser.

**Note**: The web proxy that backs `/api/search` reads `THEO_SEARCH_API_KEY` on every request. If the value starts with `Bearer`, it's forwarded as an `Authorization` header; otherwise it's sent via `X-API-Key`.

### One-Command Local Dev

Launch both API and Web services with a single command:

```powershell
./scripts/dev.ps1
```

**Options**:

```powershell
./scripts/dev.ps1 -ApiPort 8010 -WebPort 3100 -BindHost 0.0.0.0
```

Stop with Ctrl+C (automatically cleans up background jobs).

### Docker Compose

Run the full stack (Postgres + Redis + API + Web):

```powershell
cd infra
docker compose up --build -d
```

- Web UI: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- View logs: `make logs`
- Stop: `docker compose down`

---

## Configuration

### API Authentication

The API requires authentication credentials before starting. Configure one or more of the following:

- **API Keys**: Set `THEO_API_KEYS` environment variable
- **JWT Settings**: Set `THEO_AUTH_JWT_SECRET` (and optional issuer/audience)
- **Anonymous Access** (dev only): Set `THEO_AUTH_ALLOW_ANONYMOUS=1`

When anonymous access is disabled and no credentials are supplied, requests fail with HTTP 403.

### Topic Digest Notifications

Background workers can send webhooks when topic digests are generated. Configure via environment variables:

- `NOTIFICATION_WEBHOOK_URL` – Required to enable delivery (logs and skips if unset)
- `NOTIFICATION_WEBHOOK_HEADERS` – Optional JSON object of extra HTTP headers (e.g., `{ "Authorization": "Bearer …" }`)
- `NOTIFICATION_TIMEOUT_SECONDS` – Optional timeout override (default: 10 seconds)

Each notification POST includes the digest document identifier, recipient list, and context for downstream formatting.

---

## Advanced Topics

### Reranker and Intent Tagger Workflows

Early reranker and intent tagger experiments live behind feature flags to avoid impacting production retrieval quality. Review the [reranker MVP plan](docs/reranker_mvp.md) for dataset expectations and export conventions.

**Training candidate models**:

```bash
python -m theo.experiments.reranker.train --config configs/reranker.yaml
python -m theo.experiments.intent.train --config configs/intent.yaml
```

**Capturing before/after retrieval metrics**:

```bash
python -m theo.services.cli.rag_eval --dev-path data/eval/rag_dev.jsonl \
  --trace-path data/eval/production_traces.jsonl \
  --output data/eval/reranker_candidate.json
```

Document the resulting metrics in pull requests and release notes before toggling feature flags in staging or production.

### Training and Evaluating the Reranker

Synthetic fixtures for the learning-to-rank pipeline live under `tests/ranking/data`. Train a reranker on recent feedback and evaluate it on a holdout split:

**Training a checkpoint** (using the last 30 days of feedback):

```bash
python scripts/train_reranker.py \
  --feedback-path tests/ranking/data/feedback_events.jsonl \
  --model-output /tmp/reranker.joblib \
  --lookback-days 30
```

**Evaluating the checkpoint** (on a labeled holdout set at k=10):

```bash
python scripts/eval_reranker.py \
  --checkpoint /tmp/reranker.joblib \
  --holdout-path tests/ranking/data/holdout.json \
  --k 10 \
  --report-path /tmp/reranker_metrics.json
```

Use `--reference-time` on the training script to anchor the lookback window when replaying historical fixtures. The evaluation script prints baseline and reranked nDCG@k, MRR, and Recall@k metrics and optionally writes them to JSON for CI-friendly reporting.

### Database Reset and Reseeding

Rebuild the schema, apply SQL migrations, seed reference datasets, and verify the API returns seeded data:

**Unix/Linux/macOS**:

```bash
./scripts/reset_reseed_smoke.py --log-level DEBUG
```

**Windows PowerShell**:

```powershell
./scripts/reset-reseed-smoke.ps1 -LogLevel DEBUG
```

Both variants default to a local SQLite database. Provide `--database-url`/`-DatabaseUrl` for Postgres or other backends. The helper performs an authenticated GET request using an API key (`--api-key`/`-ApiKey`, defaults to `local-reset-key`) to confirm the `/research/contradictions` endpoint returns data after seeding.

### Performance Monitoring

Continuous integration runs Lighthouse to guard against client-side regressions. Review the [performance monitoring policy](docs/performance.md) for guidance on interpreting lab scores, comparing them with Core Web Vitals, and understanding thresholds that require follow-up.

---

## MCP Server Integration

The Model Context Protocol (MCP) server ships with the API and can be deployed in multiple ways:

### Option 1: Embedded in the API

Set `MCP_TOOLS_ENABLED=1` in your environment (see `.env.example`). When the main API boots, it mounts the MCP app at `http://127.0.0.1:8000/mcp`, exposing `/metadata` and `/tools/*` endpoints behind the existing authentication layer.

### Option 2: Standalone Process

Run the MCP server independently for tooling or contract tests:

```powershell
$Env:MCP_TOOLS_ENABLED = "1"
$Env:MCP_RELOAD = "1"
python -m mcp_server
```

Override `MCP_PORT` or `MCP_HOST` to change the bind address (defaults: `8050`/`127.0.0.1`).

### Option 3: Dev Script with MCP

Launch all three services (API + Web + MCP) locally:

```powershell
./scripts/dev.ps1 -IncludeMcp -ApiPort 8000 -McpPort 8050
```

### Option 4: Docker Compose

Expose the MCP server via Docker:

```powershell
docker compose up mcp  # MCP only
docker compose up      # Full stack
```

The service listens on `http://localhost:8050` by default and shares the same database and storage volumes as the API.

### Architecture

Review [`docs/adr/0001-expose-theoengine-via-mcp.md`](docs/adr/0001-expose-theoengine-via-mcp.md) for architectural decisions that guide the tool contracts and feature flags.

---

## Documentation

- **[BLUEPRINT.md](docs/BLUEPRINT.md)** – Complete system architecture and design
- **[CLI.md](docs/CLI.md)** – Command-line interface guide
- **[API.md](docs/API.md)** – API reference and endpoints
- **[MCP Integration Guide](docs/mcp_integration_guide.md)** – ChatGPT connector setup
- **[Performance Monitoring](docs/performance.md)** – Lighthouse CI and Core Web Vitals
- **[Reranker MVP Plan](docs/reranker_mvp.md)** – Dataset expectations and export conventions
- **[Test Map](docs/testing/TEST_MAP.md)** – Testing strategy and coverage

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting issues and pull requests.

## License

See the repository for license information.
