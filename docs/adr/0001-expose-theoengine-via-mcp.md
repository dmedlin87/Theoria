# ADR 0001: Expose TheoEngine via the Model Context Protocol

## Status
Accepted

## Context
TheoEngine powers a variety of research workflows that benefit from structured tool
access inside LLM-driven experiences. The Model Context Protocol (MCP) provides a
standard way to surface back-end capabilities such as document search, note taking,
and evidence retrieval. Prior experiments exposed these capabilities ad-hoc, which
made it difficult to evolve payload schemas or keep parity with the public REST API.

## Decision
We will expose TheoEngine functionality through an MCP server. The initial
capabilities focus on scripture-centric research primitives:

- `search`: retrieve passages, documents, and cross references.
- `note_write`: persist a research note anchored to a scripture reference.
- `note_list`: fetch existing research notes for a passage.

The `note_write` tool accepts an explicit `osis` anchor identifying the passage that
the note references. A `doc_id` may be supplied in addition to the anchor, but it is
only used when a lookup exists to resolve the document's dominant
`Passage.osis_ref`. Clients must always provide the `osis` anchor because it is the
value persisted alongside the note.

## Consequences
- Payload schemas for MCP tools track the REST API models, reducing schema drift.
- Client tooling can rely on the `osis` anchor being required for note creation.
- Future enhancements may add optional helpers (e.g., resolving a `doc_id`) without
  breaking existing integrations.
