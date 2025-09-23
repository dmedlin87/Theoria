# Theo Engine API

This document describes the planned API endpoints for the Theo Engine MVP. Each
endpoint is represented in the FastAPI application located at
`theo/services/api/app`.

## Ingestion

### POST /ingest/file
Upload a binary document. The API stores the binary and queues a worker task to
parse, chunk, and index the file.

### POST /ingest/url
Submit a canonical URL (web page or YouTube). The system fetches the resource
and schedules downstream parsing.

## Search

### GET /search
Hybrid search endpoint combining vector similarity and lexical ranking. Supports
optional `q` (keywords) and `osis` (Bible reference) parameters.

## Verses

### GET /verses/{osis}/mentions
Return all passages referencing the requested OSIS verse across the corpus.

## Documents

### GET /documents/{document_id}
Return a document with normalized metadata and all associated passages.
