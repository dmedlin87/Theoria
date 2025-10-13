# Search API Authentication

Theo Engine's search endpoints are protected by the same authentication layer as the rest of the FastAPI service. This guide walks through configuring credentials, choosing the correct headers, and wiring local tooling so every search request is accepted by the API gateway.

## Configure credentials

The service accepts either static API keys or JWT bearer tokens. Define at least one strategy before starting the API:

- **Static API keys** &mdash; Set the `THEO_API_KEYS` environment variable to a JSON array (e.g. `THEO_API_KEYS='["alpha","beta"]'`) or a comma-separated string (e.g. `THEO_API_KEYS="alpha,beta"`).
- **JWT bearer tokens** &mdash; Provide `THEO_AUTH_JWT_SECRET` for HMAC signatures or `THEO_AUTH_JWT_PUBLIC_KEY` / `THEO_AUTH_JWT_PUBLIC_KEY_PATH` for asymmetric signatures. Optional `THEO_AUTH_JWT_ISSUER`, `THEO_AUTH_JWT_AUDIENCE`, and `THEO_AUTH_JWT_ALGORITHMS` tighten token validation when required.

If neither strategy is configured, the API rejects requests unless `THEO_AUTH_ALLOW_ANONYMOUS=1` is explicitly enabled for isolated local testing and `THEO_ALLOW_INSECURE_STARTUP=1` is set to acknowledge the risk.

> **Important:** `THEO_ALLOW_INSECURE_STARTUP` only exists to keep developer workstations unblocked. Production and shared staging environments must supply API keys or JWT credentials and omit the override so the service refuses to boot when authentication is misconfigured. The override now fails fast unless `THEORIA_ENVIRONMENT` (or `ENVIRONMENT`) is set to `development` or `test`, preventing accidental enablement in production deployments.

## Choose the correct header

Every request to `/search` must include exactly one of the following headers:

- `Authorization: Bearer <token>` &mdash; Works for JWTs and static API keys. Tokens containing two periods (`.`) are treated as JWTs and decoded according to the JWT settings above. Tokens without periods are matched against the configured API-key allowlist.
- `X-API-Key: <token>` &mdash; Sends the raw API key without a `Bearer` prefix.

The Next.js search proxy (`theo/services/web/app/api/search/route.ts`) reads `THEO_SEARCH_API_KEY` on each request to decide which header to forward:

- Values starting with `Bearer` (case-insensitive) are forwarded unchanged as an `Authorization` header.
- Any other value is sent in the `X-API-Key` header.

This behavior lets you reuse the same environment variable across local development, server-side rendering, and hosted deployments—simply choose whether the stored secret already includes the `Bearer` prefix.

## Environment variable quick reference

| Scenario | Required variables | Header sent |
| --- | --- | --- |
| Local web UI (`npm run dev`) | `THEO_SEARCH_API_KEY` plus API credentials above | `Authorization` if value starts with `Bearer`, else `X-API-Key` |
| Direct API requests (curl, Postman) | Set the matching header manually | As provided |
| CLI / scripts (`ingest_folder`, etc.) | Export `THEO_API_KEYS` or JWT env vars before invoking | Determined by provided headers |

## Verifying your setup

1. Configure credentials via environment variables or secrets manager.
2. Start the API (`uvicorn theo.services.api.app.main:app --reload`).
3. Issue a test request:

   ```bash
   curl -H "Authorization: Bearer $THEO_SEARCH_API_KEY" \
     "http://127.0.0.1:8000/search?q=grace"
   ```

   If your token does not include the `Bearer` prefix, change the header to `X-API-Key: $THEO_SEARCH_API_KEY` instead.

A successful response returns HTTP 200 with search results. Authentication failures return HTTP 401/403 along with a diagnostic message.

For additional platform setup steps review the [repository configuration section](../README.md#configuration).
