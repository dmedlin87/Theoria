# Candidate features for retirement

This note captures feature surfaces that appear to add significant maintenance
burden without delivering user-facing value in the current deployment posture.
Each section summarizes the dormant pathways, the code they touch, and the work
required to safely remove them.

## Neo4j graph projection integration

* **Status:** Retired. The adapter, ingest hooks, and dependency pins were
  removed once we confirmed no deployments supplied Neo4j credentials.
* **Surface area:** Formerly covered the Neo4j adapter,
  `theo.application.facades.graph`, ingestion-time projection hooks, and
  optional dependency manifests.
* **Outcome:** Ingest pipelines now run without graph projection branches and
  the dependency set no longer includes the Neo4j Python driver.

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
