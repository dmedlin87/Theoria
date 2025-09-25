# Theo Engine

This repository powers Theo's document ingestion and retrieval pipeline. See [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) for the full system overview. The repository also exposes a bulk ingestion CLI that can walk a folder of source files and hand them to the API or worker pipeline.

Theo Engine now layers grounded generative workflows on top of the deterministic retrieval core:

- Securely store multiple AI provider credentials (OpenAI, Anthropic, Azure, local adapters) and register custom model presets in the admin settings API.
- Run verse-linked research, sermon prep, comparative analysis, multimedia insight extraction, devotional guides, corpus curation, and collaboration flows directly in the Verse Aggregator and search interfaces with strict OSIS-anchored citations.
- Generate export-ready deliverables (Markdown, NDJSON, CSV) for sermons, lessons, and Q&A transcripts with reproducibility manifests, and trigger post-ingest batch enrichments from the CLI.
- Monitor new theological topics via OpenAlex-enhanced clustering and receive weekly digests summarizing under-represented themes.
- Track background ingestion jobs in real time, edit document metadata inline, and surface historian notes alongside the grounded copilot workflows in the web UI.

For usage details run `python -m theo.services.cli.ingest_folder --help` or consult [the CLI guide](docs/CLI.md).

## Running the test suite

The application relies on several third-party libraries for its API, ORM, and ingestion pipeline.
Install the runtime and test dependencies before executing the tests:

```bash
pip install -r requirements.txt
```

After the dependencies are installed you can run `pytest` from the repository root to execute the automated test suite.

## Running the Web UI (Next.js frontend)

The Next.js application lives under `theo/services/web` (there is **no** `package.json` at the repository root). If you run `npm run dev` from the root you will see an error similar to:

```text
npm error enoent Could not read package.json: Error: ENOENT: no such file or directory, open '.../TheoEngine/package.json'
```

Follow these steps instead:

1. Open a terminal at the repo root (optional if you are already there):

```powershell
cd c:\Users\dmedl\Projects\TheoEngine
```

1. Start (or keep running) the API in another terminal (SQLite default):

```powershell
uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port 8000
```

1. In a new terminal start the web UI (point it at the API):

```powershell
cd .\theo\services\web
$Env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
npm install   # first time only
npm run dev
```

1. Open <http://localhost:3000> in your browser.

### Docker alternative (Postgres + Redis + API + Web)

```powershell
cd infra
docker compose up --build -d
```

Then visit <http://localhost:3000> (API docs at <http://localhost:8000/docs>). Use `make logs` for streaming logs and `docker compose down` to stop.

### One-command local dev (API + Web without Docker)

You can use the helper script to launch both services (FastAPI + Next.js) with one command:

```powershell
./scripts/dev.ps1
```

Options:

```powershell
./scripts/dev.ps1 -ApiPort 8010 -WebPort 3100 -BindHost 0.0.0.0
```

Stops with Ctrl+C (web) and automatically cleans up the API background job.
