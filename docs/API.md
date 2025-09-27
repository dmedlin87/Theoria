# Theo Engine API

Theo Engine exposes a FastAPI application located at
`theo/services/api/app`. The service is designed around JSON responses and
multipart uploads for binary content.

- **Base URL:** `/` (all paths below are relative to the FastAPI root)
- **Content type:** `application/json` unless noted otherwise
- **Authentication:** not required (the MVP runs in trusted environments)
- **Error format:** errors follow FastAPI's default structure:
  
  ```json
  {
    "detail": "Human readable message"
  }
  ```

The sections below describe each resource group, required inputs, and response
payloads.

## Ingestion

Ingestion endpoints create or update documents that are later available for
search and verse lookups. Successful requests return a
`DocumentIngestResponse`:

```json
{
  "document_id": "uuid",
  "status": "processed"
}
```

All ingestion endpoints may return **400 Bad Request** when the source is
unsupported or when frontmatter cannot be parsed.

### `POST /ingest/file`

Accepts binary uploads via `multipart/form-data`.

| Field        | Type            | Required | Notes                                   |
| ------------ | --------------- | -------- | --------------------------------------- |
| `file`       | File            | ✅       | Any supported document (PDF, DOCX, etc) |
| `frontmatter`| Text (JSON str) | ❌       | Optional metadata overrides              |

The uploaded file is stored temporarily, parsed synchronously, and indexed.

### `POST /ingest/url`

Accepts a JSON body matching `UrlIngestRequest`:

```json
{
  "url": "https://example.com/article",
  "source_type": "web",
  "frontmatter": {
    "title": "Example Article",
    "authors": ["Author"]
  }
}
```

`source_type` and `frontmatter` are optional. The backend fetches the resource
and processes it with the same pipeline as uploaded files.

### `POST /ingest/transcript`

Uploads pre-generated transcripts, optionally paired with the original audio.
The request uses `multipart/form-data` with the following fields:

| Field         | Type            | Required | Notes                                           |
| ------------- | --------------- | -------- | ----------------------------------------------- |
| `transcript`  | File            | ✅       | Transcript file (WebVTT, plain text, etc.)      |
| `audio`       | File            | ❌       | Optional audio/video binary for reference       |
| `frontmatter` | Text (JSON str) | ❌       | Optional metadata overrides                     |

The pipeline parses the transcript and indexes generated passages. Audio, when
provided, is stored long enough to support downstream enrichments.

## Background jobs

Background job endpoints enqueue asynchronous work to reprocess existing
documents. Legacy document-specific routes return **202 Accepted** with
`{ "document_id": "...", "status": "queued" }`. The generic queue endpoint
returns a deterministic descriptor that clients can cache for idempotency.

- **404 Not Found** – the requested document does not exist.
- **400 Bad Request** – the document is missing required source artifacts.

### `POST /jobs/reparse/{document_id}`

Replays the ingestion pipeline for a previously stored document. The service
locates the original source file and schedules a background worker to reparse
it.

### `POST /jobs/enrich/{document_id}`

Queues a metadata enrichment task that re-hydrates topics, provenance score, and
other derived metadata.

### `POST /jobs/topic_digest`

Generates the weekly OpenAlex-enhanced topic digest. Optional body parameters:

```json
{
  "since": "2024-08-05T00:00:00Z",
  "notify": ["alerts@theo.app"]
}
```

The task clusters new documents by `primary_topic` + top-N topics and stores a `digest` document with summary paragraphs.

### `POST /jobs/enqueue`

Queues arbitrary Celery tasks by name. Body:

```json
{
  "task": "research.enrich",
  "args": {"document_id": "doc-123", "force": true},
  "schedule_at": "2030-01-01T12:00:00Z"
}
```

Response:

```json
{
  "job_id": "018fa7c0-4c9c-7dd2-a0d1-4d53302ac160",
  "task": "research.enrich",
  "args_hash": "0ab4f5f4f33d1a9f0db13f8e4a2a77c748d9c9fdf09f9b282f2cf3bde6f84f16",
  "queued_at": "2024-07-01T15:30:00Z",
  "schedule_at": "2030-01-01T12:00:00Z",
  "status_url": "/jobs/018fa7c0-4c9c-7dd2-a0d1-4d53302ac160"
}
```

If the same `task` and normalized `args` are enqueued again within ~10 minutes,
the API replays the original payload (same `job_id`, timestamps, and
`args_hash`) and does **not** create a duplicate job. This makes retries safe
for clients without additional coordination logic.

## Search

### `GET /search`

Runs hybrid retrieval (vector + lexical) over the indexed passages. Query
parameters:

| Parameter     | Type   | Description                                   |
| ------------- | ------ | --------------------------------------------- |
| `q`           | str    | Keyword query                                  |
| `osis`        | str    | Normalized OSIS Bible reference                |
| `collection`  | str    | Restrict results to a specific collection      |
| `author`      | str    | Filter by canonical author                     |
| `source_type` | str    | Filter by document source type                 |
| `k`           | int    | Number of results to return (1 – 50, default 10)|

Example response:

```json
{
  "query": "grace and forgiveness",
  "osis": null,
  "results": [
    {
      "id": "passage-1",
      "document_id": "doc-1",
      "document_title": "Sermon on Grace",
      "text": "...",
      "snippet": "...",
      "rank": 1,
      "score": 0.92,
      "highlights": ["grace", "forgiveness"]
    }
  ],
  "debug": null
}
```

## Verse mentions

### `GET /verses/{osis}/mentions`

Returns passages that reference a specific verse. Optional query parameters
mirror the search filters: `source_type`, `collection`, and `author`.

Response:

```json
{
  "osis": "John.3.16",
  "total": 2,
  "mentions": [
    {
      "passage": {
        "id": "passage-1",
        "document_id": "doc-1",
        "text": "...",
        "osis_ref": "John.3.16",
        "score": null
      },
      "context_snippet": "..."
    }
  ]
}
```

### `GET /verses/{osis}/timeline`

Aggregates mention counts into fixed windows so clients can visualize trends.
The endpoint respects the same filters as the mentions route and is guarded by
the `verse_timeline` feature flag returned from `/features/discovery`.

Query parameters:

| Parameter     | Type   | Description                                      |
| ------------- | ------ | ------------------------------------------------ |
| `window`      | str    | Bucket size: `week`, `month`, `quarter`, `year`. |
| `limit`       | int    | Max number of windows to return (default 36).    |
| `source_type` | str    | Optional filter mirroring `/mentions`.           |
| `collection`  | str    | Optional filter mirroring `/mentions`.           |
| `author`      | str    | Optional filter mirroring `/mentions`.           |

Example response:

```json
{
  "osis": "John.3.16",
  "window": "month",
  "total_mentions": 12,
  "buckets": [
    {
      "label": "2024-01",
      "start": "2024-01-01T00:00:00+00:00",
      "end": "2024-02-01T00:00:00+00:00",
      "count": 3,
      "document_ids": ["doc-123", "doc-456"],
      "sample_passage_ids": ["passage-9"]
    }
  ]
}
```

## Creator perspectives

Creator endpoints surface stance summaries and timestamped quotes for creators
who mention a given verse or short range. The feature is guarded by the
`creator_verse_perspectives` flag returned from `/features/discovery`.

### `GET /creators/verses`

Aggregate creators and their quotes for an OSIS reference. Query parameters:

| Parameter        | Type | Description                                                    |
| ---------------- | ---- | -------------------------------------------------------------- |
| `osis`           | str  | Required OSIS reference or short range (e.g., `John.1.1-John.1.3`). |
| `limit_creators` | int  | Optional maximum creators to return (default 10, max 50).      |
| `limit_quotes`   | int  | Optional maximum quotes per creator (default 3, max 10).       |

Response:

```json
{
  "osis": "John.1.1",
  "total_creators": 2,
  "creators": [
    {
      "creator_id": "cr_123",
      "creator_name": "A. Scholar",
      "stance": "apologetic",
      "confidence": 0.62,
      "claim_count": 5,
      "stance_distribution": {"apologetic": 4, "neutral": 1},
      "quotes": [
        {
          "segment_id": "seg_456",
          "quote_md": "_In the beginning_ reflects...",
          "source_ref": "youtube:abc123#t=252",
          "osis_refs": ["John.1.1"],
          "video": {
            "video_id": "abc123",
            "title": "Logos and Creation",
            "url": "https://youtu.be/abc123",
            "t_start": 252.0
          }
        }
      ]
    }
  ],
  "meta": {
    "range": "John.1.1",
    "generated_at": "2025-02-14T12:00:00Z"
  }
}
```

### `GET /creators/verses/{osis}`

Path-based variant that accepts the OSIS reference as part of the URL. Query
parameters `limit_creators` and `limit_quotes` behave the same as the collection
endpoint.

## Research dock

Research endpoints power the study/reader dock. They respect feature flags
surfaced via `/features/discovery` so clients can hide unavailable panels.

### `GET /research/notes`

Lists saved research notes for a specific OSIS reference. Clients can layer
optional filters to narrow the response to matching stances, claim types, tags,
or a minimum confidence threshold.

Query parameters:

| Parameter         | Type   | Description                                                      |
| ----------------- | ------ | ---------------------------------------------------------------- |
| `osis`            | str    | Required OSIS anchor (e.g., `John.1.1`).                          |
| `stance`          | str    | Optional stance label filter (case-insensitive).                 |
| `claim_type`      | str    | Optional claim type filter (case-insensitive).                   |
| `tag`             | str    | Restrict to notes where `tags` contains the provided label.      |
| `min_confidence`  | float  | Minimum inclusive confidence score (`0.0` – `1.0`).              |

Example filtered response:

```http
GET /research/notes?osis=Luke.1.1&stance=investigative&tag=orderly&min_confidence=0.75
```

```json
{
  "osis": "Luke.1.1",
  "notes": [
    {
      "id": "018fa7c0-...",
      "osis": "Luke.1.1",
      "title": null,
      "stance": "investigative",
      "claim_type": "historical",
      "confidence": 0.85,
      "tags": ["preface", "orderly"],
      "body": "Detailed investigation",
      "evidences": [],
      "created_at": "2024-08-12T18:21:00Z",
      "updated_at": "2024-08-12T18:21:00Z"
    }
  ],
  "total": 1
}
```

Invalid confidence values outside `0.0` – `1.0` return **422 Unprocessable
Entity** with FastAPI's default validation payload.

### `GET /research/contradictions`

Returns seeded contradiction or harmony claims anchored to OSIS references.

Query parameters:

| Parameter | Type   | Description                                      |
| --------- | ------ | ------------------------------------------------ |
| `osis`    | list   | One or more OSIS ranges (`osis=Luke.2.1-7`).     |
| `topic`   | str    | Optional tag filter (e.g., `chronology`).        |
| `limit`   | int    | Max number of items to return (default 25).      |

Response (truncated):

```json
{
  "items": [
    {
      "id": "018fa7be-0b67-7db4-8737-7ad63a17c377",
      "osis_a": "Luke.2.1-7",
      "osis_b": "Matthew.2.1-12",
      "summary": "Luke situates Jesus' birth during the census of Quirinius while Matthew frames it around Herod's reign, creating a classic chronology tension.",
      "source": "community",
      "tags": ["chronology", "nativity"],
      "weight": 0.9
    }
  ]
}
```

When the feature flag is disabled the endpoint still returns **200 OK** with
`{"items": []}` for compatibility.

### `GET /research/geo/search`

Performs fuzzy lookup of seeded biblical places.

Query parameters:

| Parameter | Type | Description                                  |
| --------- | ---- | -------------------------------------------- |
| `query`   | str  | Partial place name (e.g., `Bethlehem`).      |
| `limit`   | int  | Max number of results (default 10).          |

Response:

```json
{
  "items": [
    {
      "slug": "bethlehem",
      "name": "Bethlehem",
      "lat": 31.7054,
      "lng": 35.2024,
      "confidence": 0.95,
      "aliases": ["Beth-lehem", "Bethlehem Ephrathah"],
      "sources": {
        "dataset": "OpenBible.info",
        "license": "CC BY 3.0"
      }
    }
  ]
}
```

### Feature discovery

`GET /features/discovery` returns a nested feature map:

```json
{
  "features": {
    "research": true,
    "contradictions": true,
    "geo": true,
    "verse_timeline": true
  }
}
```

Clients should check `features.contradictions`, `features.geo`, and
`features.verse_timeline` before
rendering the corresponding panels.

## Documents

Document endpoints expose indexed content and metadata.

### `GET /documents/`

Lists documents with pagination.

| Parameter | Type | Description                        |
| --------- | ---- | ---------------------------------- |
| `limit`   | int  | Page size (1 – 100, default 20)    |
| `offset`  | int  | Zero-based result offset (default 0)|

Response:

```json
{
  "items": [
    {
      "id": "doc-1",
      "title": "Sermon on Grace",
      "source_type": "transcript",
      "collection": "Grace Series",
      "authors": ["Jane Pastor"],
      "created_at": "2024-04-01T12:00:00Z",
      "updated_at": "2024-04-01T12:05:00Z",
      "provenance_score": 85
    }
  ],
  "total": 125,
  "limit": 20,
  "offset": 0
}
```

### `GET /documents/{document_id}`

Retrieves a single document with its normalized metadata and associated
passages. The response includes extended fields such as `source_url`, `topics`,
`metadata` (aliased as `meta`), and the embedded `passages` array. A **404 Not
Found** error is returned when the identifier is unknown.

### `GET /documents/{document_id}/passages`

Returns paginated passages for a specific document. Supports the same `limit`
and `offset` parameters as the document list endpoint and responds with
`DocumentPassagesResponse`:

```json
{
  "document_id": "doc-1",
  "passages": [
    {
      "id": "passage-1",
      "text": "...",
      "osis_ref": null,
      "page_no": 1
    }
  ],
  "total": 32,
  "limit": 20,
  "offset": 0
}
```

## Export

Export endpoints provide bulk-friendly payloads that combine metadata and
content for downstream workflows.

### `GET /export/search`

Runs the hybrid search pipeline and returns up to 1,000 ranked passages as an
export payload. Query parameters mirror `/search` with an additional `k`
parameter (default 100) controlling the number of rows.

Response:

```json
{
  "query": "grace",
  "osis": null,
  "filters": {
    "collection": "sermons",
    "author": null,
    "source_type": null
  },
  "total_results": 2,
  "results": [
    {
      "rank": 1,
      "score": 0.91,
      "passage": {
        "id": "passage-1",
        "document_id": "doc-1",
        "text": "..."
      },
      "document": {
        "id": "doc-1",
        "title": "Sermon on Grace",
        "collection": "sermons",
        "authors": ["Jane Pastor"],
        "source_type": "markdown"
      }
    }
  ]
}
```

### `GET /export/documents`

Returns documents that match optional `collection`, `author`, or `source_type`
filters. Set `include_passages=false` to omit passage payloads and use `limit`
to cap the number of returned documents (default is unlimited, maximum 1,000).

Response:

```json
{
  "filters": {
    "collection": "sermons",
    "author": null,
    "source_type": null
  },
  "include_passages": true,
  "limit": null,
  "total_documents": 1,
  "total_passages": 12,
  "documents": [
    {
      "id": "doc-1",
      "title": "Sermon on Grace",
      "collection": "sermons",
      "source_type": "markdown",
      "authors": ["Jane Pastor"],
      "passages": [
        { "id": "passage-1", "text": "..." }
      ]
    }
  ]
}
```

### `POST /export/deliverable`

Creates sermon/lesson/Q&A deliverables backed by AI syntheses and deterministic retrieval. Request body:

```json
{
  "type": "sermon",
  "source_ids": ["doc-1", "doc-2"],
  "model_preset": "gpt-4o-mini@openai",
  "formats": ["md", "ndjson", "csv"],
  "filters": {
    "osis": "Romans.8",
    "collection": "romans-series"
  }
}
```

The API immediately returns a job descriptor:

```json
{
  "export_id": "01J2Y3A7Z8X4C6V0B7N9P",
  "status": "queued",
  "formats": ["md", "ndjson", "csv"],
  "manifest_path": "/exports/01J2Y3A7Z8X4C6V0B7N9P/manifest.json"
}
```

When the job completes the assets live under `STORAGE_ROOT/exports/{export_id}/` with:

- `manifest.json` containing `export_id`, `schema_version`, `generated_at`, `filters`, `git_sha`, and `model_preset`.
- One file per requested format (`sermon.md`, `sermon.ndjson`, `sermon.csv`).

Clients may poll `GET /export/deliverable/{export_id}` to retrieve signed download URLs.

## Features

Feature discovery allows clients (CLI, Web UI) to enable or disable UI flows
without hard-coding environment variables. All feature flags are boolean.

### `GET /features`

Lists global boolean toggles.

Response:

```json
{
  "gpt5_codex_preview": true,
  "job_tracking": true,
  "document_annotations": true,
  "ai_copilot": true
}
```

### `GET /features/discovery`

Provides a structured capability map, including research sub-features. Example:

```json
{
  "features": {
    "research": true,
    "contradictions": false,
    "geo": true
  }
}
```

Use `features.contradictions` and `features.geo` to decide whether to surface
the corresponding panels in the research dock.

## Research trails

Research trails expose the persisted audit log for each agent workflow run.
They capture the stored plan, ordered steps, source citations, and the final
answer payload. Use these endpoints to inspect how a response was produced and
to replay it against the current corpus.

### `GET /trails/{trail_id}`

Returns a full `AgentTrail` record, including steps and sources:

```json
{
  "id": "01J3D9Q8PRX6M0T7V4Z2",
  "workflow": "verse_copilot",
  "status": "completed",
  "plan_md": "- Retrieve relevant passages...",
  "final_md": "[1] In the beginning...",
  "steps": [
    {
      "step_index": 0,
      "tool": "hybrid_search",
      "output_digest": "8 passages"
    },
    {
      "step_index": 1,
      "tool": "llm.generate",
      "output_digest": "628 characters"
    }
  ],
  "sources": [
    {
      "source_type": "passage",
      "reference": "passage-1",
      "meta": {
        "osis": "John.1.1",
        "anchor": "page 1"
      }
    }
  ]
}
```

### `POST /trails/{trail_id}/replay`

Replays the stored workflow with the saved inputs. Optional body:

```json
{ "model": "gpt-4o-mini" }
```

If `model` is omitted, the original configuration is reused. Response:

```json
{
  "trail_id": "01J3D9Q8PRX6M0T7V4Z2",
  "original_output": { "answer": { "summary": "..." } },
  "replay_output": { "answer": { "summary": "..." } },
  "diff": {
    "changed": false,
    "summary_changed": false,
    "added_citations": [],
    "removed_citations": []
  }
}
```

**Limitations:** token accounting (`tokens_in`, `tokens_out`) is currently left
null, and replay does not overwrite the stored `output_payload`. Clients should
persist their own comparison history if needed.

## Reference datasets & seeds

Theo Engine bundles starter datasets to light up the research dock without
external dependencies:

- `data/seeds/contradictions.json` – community-curated tensions/harmonies.
  Entries are tagged with OSIS references (stored as-is) and tagged by topic.
  Treat the dataset as non–peer-reviewed and supplement with your own notes.
- `data/seeds/geo_places.json` – normalized place names sourced from
  [OpenBible.info](https://www.openbible.info/geo/), licensed under CC BY 3.0.

The application loads these seeds during startup using idempotent upserts, so
re-running the loader is safe in every environment. Because contradictions are
anchored to OSIS ranges, queries accept single verses or ranges and the service
uses the same normalization logic as ingestion (`pythonbible`) to compute
intersections.
