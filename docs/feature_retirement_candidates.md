# Candidate features for retirement

This note captures feature surfaces that appear to add significant maintenance
burden without delivering user-facing value in the current deployment posture.
Each section summarizes the dormant pathways, the code they touch, and the work
required to safely remove them.

## Case Builder ingestion mirror

* **Status:** Permanently disabled through the `case_builder_enabled` and
  `case_builder_web_enabled` flags, both defaulting to `False` in
  [`theo/application/facades/settings.py`](../theo/application/facades/settings.py).
* **Surface area:** Dedicated API routes, ingest mirrors in
  [`theo/infrastructure/api/app/ingest/persistence.py`](../theo/infrastructure/api/app/ingest/persistence.py),
  Celery hooks, bespoke ORM models, and event contracts. Everything remains in
  place despite the feature never being enabled by default.
* **Maintenance drag:** Every ingest code path still branches to keep the mirror
  in sync, migrations keep the Case Builder tables alive, and tests must stub or
  skip Case Builder behaviour even though no production workflow relies on it.
* **Retirement plan:** Remove the feature flags and modules, drop the Case
  Builder tables via a migration, and excise the supporting tests and docs. This
  lets the ingest pipeline shed a sizeable amount of conditional logic and data
  model cruft.

## Neo4j graph projection integration

* **Status:** Hidden behind the `graph_projection_enabled` flag (default
  `False`) and disabled whenever no Neo4j credentials are configured.
* **Surface area:** Neo4j adapter under
  [`theo/adapters/graph/neo4j.py`](../theo/adapters/graph/neo4j.py), a graph
  facade, ingest-time projection hooks, and dependency pins for the Neo4j
  driver.
* **Maintenance drag:** We maintain optional dependency management, resilience
  handling, and projection tests for a pathway that falls back to a no-op in all
  default environments.
* **Retirement plan:** Delete the adapter and facade, rip the projection hooks
  from ingest, drop the Neo4j dependency, and prune the dormant tests/docs. This
  reduces ingest branching and simplifies dependency management.

## Standalone MCP FastAPI server

* **Status:** Exists as a separate FastAPI application under
  [`mcp_server/`](../mcp_server/) even though the primary API already exposes the
  underlying functionality. Runtime exposure is gated by the
  `mcp_tools_enabled` flag, which defaults to `False`.
* **Surface area:** Duplicate configuration, middleware, schema registration,
  metrics, and tool handlers. The codebase also carries a parallel test suite
  and documentation explaining how to run this server.
* **Maintenance drag:** The duplicate surface multiplies security review,
  dependency updates, and contract testing, while few (if any) deployments turn
  it on.
* **Retirement plan:** Remove the `mcp_server/` package, the CLI/task entries
  that spawn it, the associated tests, and the optional FastAPI/OpenTelemetry
  extras from dependency manifests. Document that the REST and CLI interfaces
  are the supported integration surfaces.

## Additional exploration

A sweep through the runtime settings identified other feature toggles (e.g.
`reranker_enabled`, `intent_tagger_enabled`, `creator_verse_perspectives_enabled`
for creator dashboards, and the `contradictions`/`geo`/`verse_timeline` research
endpoints). Unlike the dormant features above, these toggles are either active
by default, drive user-visible endpoints, or map to models and assets that are
regularly used in production and tests. No further obvious candidates for
retirement surfaced during this review.
