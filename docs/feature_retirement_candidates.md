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

* **Status:** Retired. The dedicated `mcp_server/` package, launch scripts, and
  supporting tests were removed in favour of the primary REST and CLI
  integrations documented in [`docs/INTEGRATIONS.md`](INTEGRATIONS.md).
* **Surface area:** The repository no longer carries duplicate configuration,
  schema registration, or tool handlers for MCP. Consumers should call the REST
  API or reuse the CLI utilities instead.

## Additional exploration

A sweep through the runtime settings identified other feature toggles (e.g.
`reranker_enabled`, `intent_tagger_enabled`, `creator_verse_perspectives_enabled`
for creator dashboards, and the `contradictions`/`geo`/`verse_timeline` research
endpoints). Unlike the dormant features above, these toggles are either active
by default, drive user-visible endpoints, or map to models and assets that are
regularly used in production and tests. No further obvious candidates for
retirement surfaced during this review.
