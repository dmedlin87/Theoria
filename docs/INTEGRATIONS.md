# Theo Engine Integrations

Theo Engine exposes first-class REST and CLI interfaces for automation. This guide summarizes the recommended entry points and references the deeper documentation that walks through authentication, payloads, and end-to-end workflows.

## REST API

* **Base URL:** `http://localhost:8000` in local development. Production deployments typically expose `/v1` versioned routes via the FastAPI service in `theo/infrastructure/api`.
* **OpenAPI docs:** <http://localhost:8000/docs> lists every route with schema definitions. The Prometheus metrics endpoint remains available at `/metrics`.
* **Reference documentation:** [`docs/API.md`](API.md) covers resource models, authentication requirements, and error handling semantics for REST clients.
* **Authentication:** Configure API keys or JWT credentials via the `THEO_API_KEYS`/`THEO_AUTH_*` environment variables before issuing requests. See [`SECURITY.md`](../SECURITY.md) for guidance.

## CLI Automations

Theo ships with Python-based CLI commands under `theo/application/services/cli` and supporting scripts in [`scripts/`](../scripts/). Highlights include:

* `python -m theo.application.services.cli.code_quality` — orchestrates linting, pytest, and type-checking gates. Defaults now target the main `theo/` package and `tests/` tree.
* `./scripts/reset_reseed_smoke.py` — reseeds demo content for smoke testing.
* `./scripts/perf/incremental_test_runner.py` — runs pytest against files impacted by recent Git changes.

For bulk ingestion and research automation, consult the historical CLI playbooks in [`docs/archive/2025-10-26_core/CLI.md`](archive/2025-10-26_core/CLI.md). The workflows mirror the public REST API, allowing you to queue ingest jobs or capture research output without relying on the removed MCP server.

## Migration Notes

The standalone Model Context Protocol (MCP) server has been retired. Existing tool integrations should call the REST API directly or reuse the CLI utilities outlined above. If you previously depended on MCP-specific environment variables (`MCP_*`), remove them from your deployment manifests and ensure your automation targets the documented REST endpoints instead.
