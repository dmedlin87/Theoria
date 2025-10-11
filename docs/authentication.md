# Search API Authentication

Theo Engine's search endpoints are protected by the same authentication layer as the rest of the FastAPI service. This guide summarizes how to configure credentials and which headers the search proxy expects so that clients, the web UI, and developer tooling can all make authenticated requests.

## Configure credentials

The API supports two authentication strategies:

- **Static API keys** defined via the `THEO_API_KEYS` environment variable. Provide either a JSON array (e.g. `THEO_API_KEYS='["alpha","beta"]'`) or a comma-separated string (e.g. `THEO_API_KEYS="alpha,beta"`).
- **JWT bearer tokens** validated with `THEO_AUTH_JWT_SECRET` (for HMAC signatures) or `THEO_AUTH_JWT_PUBLIC_KEY` / `THEO_AUTH_JWT_PUBLIC_KEY_PATH` (for RSA/EC signatures). Optional `THEO_AUTH_JWT_ISSUER`, `THEO_AUTH_JWT_AUDIENCE`, and `THEO_AUTH_JWT_ALGORITHMS` settings tighten token validation when required.

If neither strategy is configured, the API will reject requests unless `THEO_AUTH_ALLOW_ANONYMOUS=1` is explicitly enabled for isolated local testing.

## Supplying search credentials

Every request to `/search` must include either an `Authorization` or an `X-API-Key` header:

- **Authorization header** – Send `Authorization: Bearer <token>` for JWTs or API keys. Tokens containing two periods (`.`) are treated as JWTs and decoded according to the JWT settings above. Tokens without periods are matched against the configured API key allowlist.
- **X-API-Key header** – Send the raw API key in `X-API-Key` when you do not want to prefix it with `Bearer`.

The Next.js search proxy (`theo/services/web/app/api/search/route.ts`) reads `THEO_SEARCH_API_KEY` on each request to decide which header to forward:

- Values starting with `Bearer` (case-insensitive) are forwarded unchanged as an `Authorization` header.
- Any other value is sent in the `X-API-Key` header.

This behavior ensures you can reuse the same environment variable across local development, server-side rendering, and hosted deployments—simply choose whether the stored secret already includes the `Bearer` prefix.

## Quick reference

| Client | Required configuration | Header sent to `/search` |
| ------ | ---------------------- | ------------------------ |
| Web UI (`npm run dev`) | `THEO_SEARCH_API_KEY` plus API credentials above | `Authorization` if value starts with `Bearer`, else `X-API-Key` |
| API consumers | `Authorization: Bearer <jwt-or-key>` **or** `X-API-Key: <key>` | Same as request |
| CLI / scripts | Export `THEO_API_KEYS` or JWT env vars before invoking | Determined by provided headers |

For additional platform setup steps review the [repository configuration section](../README.md#configuration).
