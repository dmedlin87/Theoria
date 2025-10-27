> **Archived on 2025-10-26**

# Theoria MCP Integration Execution Guide

This guide turns the high-level MCP integration plan into a concrete runbook for operators and developers. It covers the full lifecycle from standing up the Theoria stack through validating the exposed Model Context Protocol tools and documenting the connector for ChatGPT.

---

## 1. Provision Theoria services with required credentials

1. Copy `infra/.env.example` to a working file (for example `infra/.env.local`). Fill in:
   - `POSTGRES_*` settings and enable the `pgvector` and `pg_trgm` extensions (Docker Compose will run `init.sql` automatically).
   - `REDIS_URL` that points at the Redis service supplied by Docker Compose.
   - `THEO_STORAGE_PATH` with a persistent folder mounted into the API/worker containers.
   - Embedding model configuration (`EMBEDDING_MODEL`, `EMBEDDING_API_BASE`, `EMBEDDING_API_KEY`), or fall back to the default BGE-M3 settings packaged with Theoria for local experiments.
2. Configure API auth before launching services:
   - Provide at least one API key via `THEO_API_KEYS="local-dev-key"`, or set `THEO_AUTH_ALLOW_ANONYMOUS=1` when running isolated local smoke tests.
   - If JWT auth is required, set `THEO_AUTH_JWT_SECRET` and corresponding issuer/audience values.
3. Launch the core stack. Either run `docker compose --file infra/docker-compose.yml up --build` or use the convenience scripts (`./scripts/dev.ps1` in PowerShell or `./scripts/run.sh` in Bash). Ensure the following services report healthy status:
   - `api` – FastAPI application that serves REST requests and Celery task submissions.
   - `web` – Next.js web client (optional for MCP-only integrations but helpful for manual validation).
   - `worker` – Celery worker consuming ingestion and indexing jobs.
   - `redis` and `postgres` – backing services required by the API and worker.

## 2. Activate MCP server with stable schema URLs

1. Start the MCP FastAPI application defined at `mcp_server/server.py`. For Docker-based workflows, add a new service that runs `uvicorn mcp_server.server:app --host 0.0.0.0 --port 8081` with the same environment file used by the API.
2. Set `MCP_SCHEMA_BASE_URL` to the externally reachable base URL of the MCP deployment (for example `https://Theoria.example.com/mcp`). This value is used to build `$id` and `$ref` fields inside `/metadata` responses so ChatGPT can dereference schemas.
3. Document the required headers for connector clients. Every request to `/tools/*` must include:
   - `X-End-User-Id` (string UUID or opaque identifier for the ChatGPT session).
   - Optional `X-Tenant-Id` if multi-tenant separation is required.
   - `X-Idempotency-Key` for write operations to guarantee safe retries.
4. Smoke test the MCP server locally: `curl http://localhost:8081/metadata` should return a JSON payload whose `tools` array matches the definitions in `mcp_server/server.py` and whose `$ref` values start with the configured `MCP_SCHEMA_BASE_URL`.

## 3. Seed Theoria with representative content

1. Prepare a starter corpus in a local folder that includes multiple source modalities:
   - PDF or DOCX files referencing well-known scripture (e.g., `John 1:1`).
   - Markdown or text files containing footnotes and OSIS references.
   - Audio/Video transcripts (plain text or JSON) to exercise quote lookup.
2. Run the ingestion CLI from the repository root (it connects directly to the
   configured database when operating in the default `api` mode):
   ```bash
   python -m theo.infrastructure.cli.ingest_folder /path/to/corpus \
     --batch-size 5 \
     --meta collection=seed_corpus
   ```
   Set any required environment variables (for example `THEO_API_KEYS`,
   database credentials, or storage paths) before executing the command. Use
   `--dry-run` to review detected metadata without persisting records, or pass
   `--mode worker` if you prefer to enqueue Celery jobs instead of running the
   ingestion pipeline inline.
3. Monitor Celery worker logs to ensure parsing and chunking jobs finish. Once complete, verify passage counts via `GET /admin/passage-count` (if enabled) or by querying the `documents` and `passages` tables directly.

## 4. Exercise MCP read tools with live data

1. **search_library** – POST an example payload and confirm hybrid search highlights:
   ```bash
   curl -X POST http://localhost:8081/tools/search_library \
     -H "Content-Type: application/json" \
     -H "X-End-User-Id: local-dev" \
     -d '{
       "query": "Logos John 1:1",
       "limit": 5,
       "filters": {"osis": ["John.1.1"]}
     }'
   ```
2. **aggregate_verses** – Request a verse range and ensure the concatenated text matches scripture content stored in the database.
3. **get_timeline** – Supply an OSIS reference and inspect the returned bucket counts and HTML labels.
4. **quote_lookup** – Test both OSIS-driven and explicit quote ID lookups to confirm transcripts were indexed correctly.
5. Capture sample responses as JSON fixtures for future regression tests or documentation snippets.

## 5. Harden MCP write tool flows

1. Decide on production guardrails:
   - `MCP_WRITE_ALLOWLIST` can restrict which `X-End-User-Id` or `X-Tenant-Id` values may perform writes.
   - `MCP_WRITE_RATE_LIMITS` defines per-user quotas in `<requests>/<seconds>` format (e.g., `note_write=20/60`).
2. Validate **note_write** in preview and commit modes:
   - Preview requests omit the `commit` flag and should return the generated note body without persisting.
   - Commit requests set `commit=true` and require an idempotency key; confirm the response includes a new note ID and the database reflects the change.
3. Trigger **index_refresh** and ensure the Celery worker enqueues an index rebuild job.
4. Call **evidence_card_create** with a mix of OSIS anchors and freeform notes, verifying any guardrails around scripture references are enforced.

## 6. Document and smoke-test ChatGPT MCP integration

1. Draft operator documentation (for example under `docs/connector/README.md`) outlining how to register the Theoria connector inside ChatGPT developer mode. Include:
   - The public `/metadata` URL and schema base.
   - Required headers and how to supply them when configuring the connector.
   - A list of available tools with brief descriptions and example prompts.
2. Provide ready-to-run `curl` scripts or Postman collections that mirror the requests exercised above. Store them alongside the documentation so engineers can run smoke tests after deployments.
3. Maintain a lightweight automated check (GitHub Action or local script) that pings `/metadata` and one read tool to ensure the connector remains functional after code or infrastructure changes.

---

Following this runbook will produce a fully operational Theoria MCP deployment that ChatGPT can use for hybrid search, verse aggregation, timeline analysis, and research note workflows.
