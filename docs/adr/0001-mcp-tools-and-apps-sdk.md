# ADR 0001: MCP Tools and Apps SDK Integration

## Status
Proposed

## Context
Theo Engine is adding Model Context Protocol (MCP) tools to expose the
established FastAPI capabilities through the Apps SDK. The API already delivers
search, research, and background job management functionality that we intend to
wrap with MCP tools so that first- and third-party experiences can reuse the
existing business logic without bypassing server-side policy enforcement.

## Decision
### Tooling Surface
| Tool | Description | Backend entrypoint | Notes |
| --- | --- | --- | --- |
| `search` | Hybrid keyword+vector retrieval with optional reranking. | `GET /search` → `hybrid_search` | Reuses the existing request model and reranker cache from the FastAPI route. 【F:theo/services/api/app/routes/search.py†L42-L108】
| `scripture_lookup` | Retrieve passages with translation metadata. | `GET /research/scripture` → `fetch_passage` | Returns validated verses via the existing research models. 【F:theo/services/api/app/routes/research.py†L41-L59】【F:theo/services/api/app/research/__init__.py†L1-L18】
| `cross_references` | Locate cross references for a verse. | `GET /research/crossrefs` → `fetch_cross_references` | Limits are surfaced as tool arguments. 【F:theo/services/api/app/routes/research.py†L62-L76】【F:theo/services/api/app/research/__init__.py†L1-L18】
| `variants_apparatus` | Retrieve textual variants for an OSIS range. | `GET /research/variants` → `variants_apparatus` | Exposes category filters and pagination. 【F:theo/services/api/app/routes/research.py†L79-L109】【F:theo/services/api/app/research/__init__.py†L14-L18】
| `dss_links` | Fetch Dead Sea Scrolls parallels. | `GET /research/dss-links` → `fetch_dss_links` | Returns structured DSS links with counts. 【F:theo/services/api/app/routes/research.py†L112-L126】【F:theo/services/api/app/research/__init__.py†L16-L18】
| `reliability_overview` | Summarise reliability bullets for a verse. | `GET /research/overview` → `build_reliability_overview` | Requires DB session injection in the tool shim. 【F:theo/services/api/app/routes/research.py†L129-L148】【F:theo/services/api/app/research/__init__.py†L11-L15】
| `morphology` | Return morphology tokens. | `GET /research/morphology` → `fetch_morphology` | JSON schema derived from existing token model. 【F:theo/services/api/app/routes/research.py†L151-L162】【F:theo/services/api/app/research/__init__.py†L5-L9】
| `research_notes` | CRUD operations for anchored research notes. | `GET/POST/PATCH/DELETE /research/notes` → `get_notes_for_osis`, `create_research_note`, `update_research_note`, `delete_research_note` | Tool set will provide `list`, `create`, `update`, and `delete` sub-commands aligned to the REST handlers. 【F:theo/services/api/app/routes/research.py†L165-L231】【F:theo/services/api/app/research/__init__.py†L5-L13】
| `historicity_search` | Citation lookup with filters. | `GET /research/historicity` → `historicity_search` | Rejects invalid year ranges before delegating. 【F:theo/services/api/app/routes/research.py†L234-L258】【F:theo/services/api/app/research/__init__.py†L16-L18】
| `fallacy_detector` | Run fallacy detection over narrative text. | `POST /research/fallacies` → `fallacy_detect` | Uses same validation as HTTP endpoint. 【F:theo/services/api/app/routes/research.py†L267-L287】【F:theo/services/api/app/research/__init__.py†L4-L6】
| `research_report` | Assemble comprehensive research reports. | `POST /research/report` → `report_build` | Surface optional fallacy inclusion and limits. 【F:theo/services/api/app/routes/research.py†L290-L314】【F:theo/services/api/app/research/__init__.py†L12-L17】
| `contradictions` | Enumerate contradictions by verse/topic. | `GET /research/contradictions` → `search_contradictions` | Honors existing feature toggle in settings. 【F:theo/services/api/app/routes/research.py†L317-L347】【F:theo/services/api/app/research/__init__.py†L2-L4】
| `commentaries` | Retrieve commentary excerpts. | `GET /research/commentaries` → `search_commentaries` | Maintains OSIS anchoring semantics. 【F:theo/services/api/app/routes/research.py†L350-L378】【F:theo/services/api/app/research/__init__.py†L1-L3】
| `geo_search` | Geographic lookup for place names. | `GET /research/geo/search` → `lookup_geo_places` | Conditional on geo feature flag. 【F:theo/services/api/app/routes/research.py†L381-L398】【F:theo/services/api/app/research/__init__.py†L4-L7】
| `geo_for_verse` | Geographic lookup for verses. | `GET /research/geo/verse` → `places_for_osis` | Returns cached geo overlays when enabled. 【F:theo/services/api/app/routes/research.py†L401-L409】【F:theo/services/api/app/research/__init__.py†L4-L7】
| `jobs_inspect` | Enumerate and inspect ingestion jobs. | `GET /jobs` / `GET /jobs/{job_id}` → `_serialize_job` | Surfaces job metadata and status. 【F:theo/services/api/app/routes/jobs.py†L70-L118】【F:theo/services/api/app/routes/jobs.py†L47-L68】
| `jobs_enqueue` | Enqueue ingestion, enrichment, or maintenance tasks. | `/jobs/reparse`, `/jobs/enrich`, `/jobs/refresh-hnsw`, `/jobs/summaries`, `/jobs/topic_digest`, `/jobs/validate_citations`, `/jobs/enqueue` | Provides typed wrappers over Celery-backed tasks while preserving idempotency guarantees. 【F:theo/services/api/app/routes/jobs.py†L121-L402】

### JSON Schemas
All MCP tool input/output schemas will be generated from the existing
Pydantic models used by the HTTP routes, guaranteeing parity with current
validation rules. For example, `HybridSearchRequest`/`HybridSearchResponse` and
`JobEnqueueRequest`/`JobStatus` already describe the payloads we need to
surface. 【F:theo/services/api/app/models/search.py†L5-L39】【F:theo/services/api/app/models/jobs.py†L15-L114】

### Authentication Propagation
MCP tool adapters will forward `end_user_id` and optional tenant metadata to the
FastAPI layer using the existing authentication strategy:

* Include `end_user_id` and `tenant_id` (when provided by the Apps SDK) as
  headers in outbound requests, ensuring auditability in API logs.
* When acting as a server-side shim, enrich the FastAPI request context with the
  resolved principal so that downstream functions (e.g., DB session filters) can
  apply tenant scoping before querying shared tables.
* Reject requests without an `end_user_id` unless `auth_allow_anonymous` is true
  in settings, mirroring current API behaviour. 【F:theo/services/api/app/core/settings.py†L52-L118】

### Logging and Redaction
* Reuse the structured logging already wired into the FastAPI routes (e.g.
  `logging.getLogger(__name__)` in `search.py`) to capture tool invocations
  without duplicating instrumentation. 【F:theo/services/api/app/routes/search.py†L23-L45】
* Ensure tool adapters scrub sensitive fields (`body` for research notes,
  `narrative_text` for reports) before logging payloads. Redaction will occur in
  the tool layer so that only metadata (IDs, counts) enters central logs.
* Retain evidence of reranker failures and job enqueue errors by forwarding the
  existing log events raised by the underlying routes/tasks.

### Rollout and Feature Flags
1. Guard all MCP tool registrations behind a new `mcp_tools_enabled` flag in the
   Apps SDK configuration so that we can dark-launch in staging.
2. Respect existing service toggles (e.g., `contradictions_enabled`, `geo_enabled`)
   when wiring tools; the adapter must probe the FastAPI settings endpoint before
   enabling optional tools in clients. 【F:theo/services/api/app/routes/research.py†L319-L398】
3. Roll out in phases: search → research basics → advanced research → job
   management. Each phase will promote from internal dogfood to partner preview
   before GA, with telemetry monitored through the shared logger and job metrics.

## Consequences
* Apps SDK consumers can reuse Theo Engine capabilities without reimplementing
  business logic, ensuring consistent validation and throttling.
* Maintenance cost drops because JSON schemas and input validation stay unified
  between HTTP and MCP surfaces.
* Feature-flag-driven rollout reduces blast radius when introducing new tools.

## Open Questions & Owners
| Question | Proposed resolution | Owner |
| --- | --- | --- |
| What persistent store should back the MCP source registry? | Evaluate reuse of the existing document storage bucket to avoid duplicating lifecycle jobs; confirm read-only API for MCP clients. | Infra Platform |
| Where should evidence cards authored via MCP live? | Extend the research notes persistence so that evidence cards are stored alongside notes with a `tool_origin` tag. | Apps SDK & Research |

Future pull requests should reference this ADR when implementing the MCP tool
layer, ensuring the adapters remain aligned with the documented backend
contracts and rollout plan.
