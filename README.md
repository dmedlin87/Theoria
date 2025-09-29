# Theo Engine

This repository powers Theo's document ingestion and retrieval pipeline. See [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) for the full system overview. The repository also exposes a bulk ingestion CLI that can walk a folder of source files and hand them to the API or worker pipeline.

Theo Engine now layers grounded generative workflows on top of the deterministic retrieval core:

- Securely store multiple AI provider credentials (OpenAI, Anthropic, Azure, local adapters) and register custom model presets in the admin settings API.
- Run verse-linked research, sermon prep, comparative analysis, multimedia insight extraction, devotional guides, corpus curation, and collaboration flows directly in the Verse Aggregator and search interfaces with strict OSIS-anchored citations.
- Generate export-ready deliverables (Markdown, NDJSON, CSV) for sermons, lessons, and Q&A transcripts with reproducibility manifests, and trigger post-ingest batch enrichments from the CLI.
- Monitor new theological topics via OpenAlex-enhanced clustering and receive weekly digests summarizing under-represented themes.
- Track background ingestion jobs in real time, edit document metadata inline, and surface historian notes alongside the grounded copilot workflows in the web UI.

For usage details run `python -m theo.services.cli.ingest_folder --help` or consult [the CLI guide](docs/CLI.md).

## API authentication configuration

The API refuses to start unless authentication credentials are configured. Set one or more
API keys via `THEO_API_KEYS` or provide JWT settings (`THEO_AUTH_JWT_SECRET` and optional
issuer/audience) **before** booting the FastAPI service. For automated tests or local
exploration you can opt into anonymous access by exporting `THEO_AUTH_ALLOW_ANONYMOUS=1`.
When anonymous access is disabled and no credentials are supplied, requests now fail with
HTTP 403.

## Performance monitoring

Continuous integration runs Lighthouse to guard against client-side regressions. Review [the performance monitoring policy](docs/performance.md) for guidance on interpreting lab scores, comparing them with Core Web Vitals, and understanding the thresholds that require follow-up.

## Running the test suite

The application relies on several third-party libraries for its API, ORM, and ingestion pipeline.
Install the runtime and test dependencies before executing the tests:

```bash
pip install -r requirements.txt
```

After the dependencies are installed you can run `pytest` from the repository root to execute the automated test suite.

## Resetting and reseeding the API database

Use the bundled helper to rebuild the schema, apply the raw SQL migrations, seed reference
datasets, and verify the API is able to return the seeded contradiction data. The script accepts
optional overrides for the database URL, migration directory, log level, and smoke test OSIS
reference.

```bash
# Unix-like environments
./scripts/reset_reseed_smoke.py --log-level DEBUG

# Windows PowerShell
./scripts/reset-reseed-smoke.ps1 -LogLevel DEBUG
```

Both variants default to a local SQLite database. Provide `--database-url`/`-DatabaseUrl` when
testing against Postgres or other backends. The helper performs an authenticated GET request using
an API key supplied via `--api-key`/`-ApiKey` (defaults to `local-reset-key`) to confirm the
`/research/contradictions` endpoint returns data after seeding.

## Configuring topic digest notifications

Background workers can send a webhook each time a topic digest is generated. Configure the delivery endpoint via environment variables (they map directly to fields in `Settings`).

- `NOTIFICATION_WEBHOOK_URL` – required to enable delivery. When unset the worker logs the attempt and skips dispatching.
- `NOTIFICATION_WEBHOOK_HEADERS` – optional JSON object of extra HTTP headers (for example `{ "Authorization": "Bearer …" }`).
- `NOTIFICATION_TIMEOUT_SECONDS` – optional float override for the HTTP timeout (defaults to 10 seconds).

Each notification POST includes the digest document identifier, the recipient list supplied to the task, and any extra context so downstream systems can format the alert.

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
$Env:THEO_SEARCH_API_KEY = "Bearer <search-api-token>"  # omit "Bearer" to send the key via X-API-Key
npm install   # first time only
npm run dev
```

The web proxy that backs `/api/search` reads `THEO_SEARCH_API_KEY` on every request. If the value starts with `Bearer` the proxy
forwards it as an `Authorization` header; otherwise it is sent via `X-API-Key`. Missing the environment variable will cause the
proxy to surface `401 Unauthorized` responses from the upstream API.

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
