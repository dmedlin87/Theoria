# Theoria

**A modern research engine for theology** that indexes your library (papers, notes, YouTube transcripts, audio), normalizes Scripture references (OSIS), and provides deterministic, verse-anchored search with AI-powered insights.

## ✨ Highlights

- 🔍 **Hybrid Search** – Semantic + lexical search with pgvector embeddings
- 📖 **Scripture-Anchored** – Automatic OSIS normalization and verse aggregation
- 🤖 **AI Workflows** – Sermon prep, comparative analysis, devotional guides with strict citations
- 🎨 **Modern UI** – Professional animations, dark mode, command palette (⌘K)
- ♿ **Accessible** – WCAG 2.1 AA compliant with keyboard navigation
- 📱 **PWA Ready** – Installable as native app on desktop and mobile
- ⚡ **Fast** – GPU-accelerated animations, optimized performance
- 🔌 **MCP Integration** – Connect to ChatGPT and other AI tools

## 📚 Quick Links

- **[System Architecture](docs/BLUEPRINT.md)** – Complete design and architecture
- **[Codebase Review](docs/CODEBASE_REVIEW.md)** – Current implementation overview and documentation index
- **[Getting Started](#quick-start)** – Run locally in minutes
- **[UI Demo](http://localhost:3000/demo-animations)** – See animations live (after starting dev server)
- **[API Documentation](http://localhost:8000/docs)** – Interactive API explorer
- **[Case Builder v4](case%20builder%20v4.md)** – Latest specifications

## 🎉 What's New

### Recent Enhancements

- ✨ **Animation System** – 10 components enhanced with context-aware animations (bounce, shake, pulse)
- 🎨 **Theme Toggle** – User-selectable light/dark/auto themes with smooth transitions
- ⌨️ **Command Palette** – Fast keyboard navigation with ⌘K/Ctrl+K shortcut
- 📱 **PWA Manifest** – Install Theoria as a native app on any device
- ♿ **Accessibility** – Full WCAG 2.1 AA compliance with reduced motion support

See [ANIMATION_ENHANCEMENTS_COMPLETE.md](ANIMATION_ENHANCEMENTS_COMPLETE.md) for complete details.

## Features

### Core Capabilities

- **Document Ingestion** – Ingest local files, URLs, and YouTube content with automatic parsing, chunking, and citation preservation
- **Scripture Normalization** – Detect and normalize Bible references to OSIS format (e.g., `John.1.1`)
- **Hybrid Search** – Combine pgvector embeddings with lexical search for optimal retrieval
- **Verse Aggregator** – View every snippet across your corpus for any OSIS reference, with jump links to original sources
- **Bulk CLI** – Walk folders of source files and submit them to the API or worker pipeline

### Generative AI Workflows

Theoria layers grounded generative capabilities on top of the deterministic retrieval core:

- **Multi-Provider Support** – Securely store credentials for OpenAI, Anthropic, Azure, and local adapters; register custom model presets via the admin API
- **Verse-Linked Research** – Run sermon prep, comparative analysis, multimedia insight extraction, devotional guides, and collaboration flows with strict OSIS-anchored citations
- **Export Deliverables** – Generate Markdown, NDJSON, and CSV exports for sermons, lessons, and Q&A transcripts with reproducibility manifests
- **Topic Monitoring** – Track emerging theological topics via OpenAlex-enhanced clustering with weekly digest notifications
- **Real-Time Tracking** – Monitor background ingestion jobs, edit document metadata inline, and surface historian notes in the web UI

### Modern User Interface

Theoria features a polished, accessible web interface with modern UX enhancements:

- **Professional Animations** – Context-aware animations throughout (bounce for success, shake for errors, pulse for active states)
- **Theme Customization** – User-selectable light/dark/auto themes with smooth transitions and persistent preferences
- **Command Palette** – Keyboard-first navigation with ⌘K/Ctrl+K shortcut for instant access to all features
- **PWA Support** – Installable as a native app on desktop and mobile with offline capabilities
- **Accessibility First** – WCAG 2.1 AA compliant with screen reader support, keyboard navigation, and reduced motion preferences
- **Loading Feedback** – Shimmer skeletons, rotating spinners, and staggered list animations for clear visual feedback
- **Responsive Design** – Mobile-first approach with adaptive layouts for all screen sizes

### Feature Matrix

| Feature | Description | Status |
|---------|-------------|--------|
| 📁 **Local File Ingestion** | PDF, DOCX, TXT, Markdown | ✅ Stable |
| 🌐 **URL Ingestion** | Web pages, YouTube transcripts | ✅ Stable |
| 🔍 **Hybrid Search** | Semantic + lexical with pgvector | ✅ Stable |
| 📖 **OSIS Normalization** | Automatic Scripture reference detection | ✅ Stable |
| 📊 **Verse Aggregator** | Corpus-wide verse snippet collection | ✅ Stable |
| 🤖 **AI Workflows** | Sermon prep, analysis, devotionals | ✅ Stable |
| 🎨 **Animations** | Context-aware UI micro-interactions | ✅ Stable |
| 🌓 **Dark Mode** | User-selectable themes | ✅ Stable |
| ⌨️ **Command Palette** | Keyboard navigation (⌘K) | ✅ Stable |
| 📱 **PWA Support** | Installable native app | ✅ Stable |
| 🔌 **MCP Integration** | ChatGPT connector | ✅ Stable |
| 📈 **Topic Monitoring** | OpenAlex clustering | ✅ Stable |
| 🔄 **Real-Time Jobs** | WebSocket job tracking | ✅ Stable |

### Getting Started

- **CLI Usage**: Run `python -m theo.services.cli.ingest_folder --help` or see the [CLI guide](docs/CLI.md)
- **MCP Integration**: Follow the [MCP integration execution guide](docs/mcp_integration_guide.md) for ChatGPT connector setup
- **Search API Authentication**: Review the [authentication guide](docs/authentication.md) for the `Authorization` vs `X-API-Key` header contract and environment configuration
- **UI Features**: Press ⌘K/Ctrl+K for command palette, toggle theme in footer, visit `/demo-animations` for live showcase

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

Execute the automated Python test suite from the repository root:

```bash
pytest -q
```

Additional targeted checks are available once dependencies are installed:

- **pgvector-backed flows** – append `--use-pgvector` (or set
  `PYTEST_USE_PGVECTOR=1`) to boot a Postgres + pgvector container for the
  ingestion and search pipelines.
- **Frontend unit tests** – from `theo/services/web`, run `npm test` for the
  legacy Jest harness or `npm run test:vitest` for the Vitest suite and coverage
  enforcement.
- **Playwright smoke tests** – from `theo/services/web`, execute
  `npm run test:e2e:smoke` to exercise the tagged end-to-end journeys. The
  `npm run test:e2e:full` target runs the complete regression matrix.

See [CONTRIBUTING.md](CONTRIBUTING.md) for a full testing matrix and guidance on
optional property and worker retry suites.

### Running the API

Before launching the server you must configure authentication for the API by either providing an API key or explicitly enabling anonymous access. Set one of the following environment variables in your shell:

```bash
export THEO_API_KEYS='["local-dev-key"]'
# or
export THEO_AUTH_ALLOW_ANONYMOUS=1
```

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

### UI Component Toolkit

The React application standardizes accessible overlays, menus, and notifications with Radix UI primitives (`@radix-ui/react-dialog`, `@radix-ui/react-dropdown-menu`, `@radix-ui/react-tooltip`, and `@radix-ui/react-toast`). Shared wrappers live under [`app/components/ui`](theo/services/web/app/components/ui) so feature components can consume consistent tokens, keyboard behaviour, and screen-reader semantics without re-implementing focus management.

#### Animation System

All UI animations are CSS-based (GPU-accelerated) with zero JavaScript overhead. The animation utilities in [`styles/animations.css`](theo/services/web/styles/animations.css) provide reusable classes for:

- **Entrance effects**: `fade-in`, `slide-up`, `slide-down`, `scale-in`
- **Attention grabbers**: `bounce`, `shake`, `pulse`
- **Loading states**: `spin`, `shimmer`, `stagger-item`
- **Reduced motion**: Automatically respects user preferences

Visit `/demo-animations` in the web UI for a live showcase of all available animations.

#### Theme System

The design system in [`app/theme.css`](theo/services/web/app/theme.css) uses CSS custom properties for theme-aware colors, shadows, and transitions. Users can toggle between light, dark, and auto (system) modes via the theme toggle in the footer. Theme preferences persist across sessions using localStorage.

#### Research modes in the web UI

The Next.js frontend exposes a `ModeProvider`/`useMode` pair that keeps the selected research mode in sync with storage and refreshes queries when users switch contexts. All components should import these helpers from [`theo/services/web/app/mode-context.tsx`](theo/services/web/app/mode-context.tsx), which is the canonical context implementation.

### One-Command Local Dev

Launch both API and Web services with a single command:

```powershell
./scripts/dev.ps1
```

**Options**:

```powershell
./scripts/dev.ps1 -ApiPort 8010 -WebPort 3100 -BindHost 0.0.0.0
```

For Bash environments, the companion script launches both services with sensible defaults:

```bash
./scripts/run.sh
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

The API requires authentication credentials before starting. If neither API keys nor JWT settings are present and anonymous access is disabled, the service aborts during startup with an authentication error. Configure one or more of the following to run the API successfully:

- **API Keys**: Set `THEO_API_KEYS` environment variable
- **JWT Settings**: Set `THEO_AUTH_JWT_SECRET` (and optional issuer/audience)
- **Anonymous Access** (dev only): Set `THEO_AUTH_ALLOW_ANONYMOUS=1`

Either supplying credentials or enabling anonymous access resolves the startup failure and allows requests to succeed.

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

Continuous integration runs Lighthouse to guard against client-side regressions. Review the [performance monitoring policy](docs/performance.md) for guidance on interpreting lab scores, comparing them with Core Web Vitals, and understanding thresholds that require follow-up. The GitHub Action summarizes deltas against the committed baseline so authors can capture the numbers, note hypotheses for any discrepancies, and coordinate load-test requests in the pull request template before requesting review.

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

### Architecture & Design

- **[BLUEPRINT.md](docs/BLUEPRINT.md)** – Complete system architecture and design
- **[ADR Directory](docs/adr/)** – Architectural decision records
- **[Case Builder v4](case%20builder%20v4.md)** – Latest case builder specifications

### Usage Guides

- **[CLI.md](docs/CLI.md)** – Command-line interface guide
- **[API.md](docs/API.md)** – API reference and endpoints
- **[MCP Integration Guide](docs/mcp_integration_guide.md)** – ChatGPT connector setup
- **[Authentication Guide](docs/authentication.md)** – API key and JWT configuration

### UI Enhancements

- **[Animation Enhancements](ANIMATION_ENHANCEMENTS_COMPLETE.md)** – Complete animation system documentation
- **[UI Overhaul Summary](UI_OVERHAUL_SUMMARY.md)** – Design system refresh details
- **[UI Loading Improvements](UI_LOADING_IMPROVEMENTS.md)** – Loading state patterns
- **[Navigation Improvements](NAVIGATION_IMPROVEMENTS.md)** – Navigation UX enhancements

### Quality & Testing

- **[Performance Monitoring](docs/performance.md)** – Lighthouse CI and Core Web Vitals
- **[Test Map](docs/testing/TEST_MAP.md)** – Testing strategy and coverage
- **[Reranker MVP Plan](docs/reranker_mvp.md)** – Dataset expectations and export conventions
- **[Security](SECURITY.md)** – Security policies and threat model

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting issues and pull requests.

## License

See the repository for license information.
