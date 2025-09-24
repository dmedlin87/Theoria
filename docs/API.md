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

## Settings & AI Providers

### `GET /ai/models`

Lists registered model presets. Responses include provider metadata, token limits, and guardrail flags:

```json
[
  {
    "id": "gpt-4o-mini@openai",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "max_output_tokens": 2000,
    "supports_citations": true,
    "cost": {
      "input_per_million": 5.0,
      "output_per_million": 15.0
    }
  }
]
```

### `POST /ai/chat`

Initiates a grounded conversation using the selected preset. Request body:

```json
{
  "model_preset": "gpt-4o-mini@openai",
  "messages": [
    { "role": "system", "content": "optional override" },
    { "role": "user", "content": "Summarise John 1:1" }
  ],
  "retrieval_filters": {
    "osis": "John.1.1-5",
    "collection": "sermons"
  }
}
```

Response:

```json
{
  "model_preset": "gpt-4o-mini@openai",
  "answer": "In the beginning...",
  "citations": [
    {
      "osis": "John.1.1",
      "document_id": "doc-1",
      "anchor_type": "page",
      "anchor_value": "12"
    }
  ],
  "retrieval_snapshot": {
    "passage_ids": ["passage-1"],
    "filters": { "osis": "John.1.1-5" }
  }
}
```

If a provider reply omits citations or references unsupported OSIS ranges the endpoint returns **422 Unprocessable Entity**.

### `PUT /settings/ai/providers/{provider}`

Upserts provider credentials. Example payload for OpenAI:

```json
{
  "api_key": "sk-...",
  "base_url": "https://api.openai.com/v1",
  "default_model": "gpt-4o-mini",
  "extra_headers": {
    "OpenAI-Organization": "org-123"
  }
}
```

Keys are stored encrypted. The API responds with the provider id and masked metadata. Only admin-authenticated clients may call this endpoint.

## Background jobs

Background job endpoints enqueue asynchronous work to reprocess existing
documents. They return **202 Accepted** with `{ "document_id": "...", "status": "queued" }`.

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

Lists currently enabled features.

Response:

```json
{
  "gpt5_codex_preview": true
}
```

Fields:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `gpt5_codex_preview` | bool | GPT-5-Codex (Preview) endpoints and UI unlocked for all clients. |

