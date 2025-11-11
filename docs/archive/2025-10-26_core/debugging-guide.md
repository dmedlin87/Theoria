> **Archived on 2025-10-26**

# End-to-End Debugging Guide

This guide explains how to follow a user request from the front-end through the
Theoria API telemetry and into the persistence layer. The instructions lean
on the trace propagation work that surfaces a single identifier across the UI,
structured API logs, emitted spans, and database records.

## 1. Capture the trace ID in the UI

1. Trigger the workflow from the UI (for example, upload content or run a
   retrieval request).
2. If the UI reports an error, open the error callout and copy the **Trace ID**
   that appears in the details modal.
   - The web client automatically inspects error responses for trace metadata,
     preferring the `debug_report_id` field in the JSON payload or any of the
     `x-debug-report-id`, `x-trace-id`, and `x-request-id` headers.
   - The parsed trace identifier is stored alongside the error state so it can
     be surfaced in the UI and in subsequent retries.

> **Where this comes from:** The shared `parseErrorResponse` helper decodes the
> trace identifier from headers or JSON bodies, and the ingestion screens keep
> the `traceId` on the error state that powers the callout component.【F:theo/services/web/app/lib/errorUtils.ts†L3-L86】【F:theo/services/web/app/upload/page.tsx†L1-L185】

## 2. Locate the matching API log entry

1. Search your API logs for the copied Trace ID.
2. The `ErrorReportingMiddleware` attaches `debug_report_id` to error
   responses and logs a structured `api.debug_report` entry that includes the
   same identifier in its payload.
3. The debug report contains the request method, URL, filtered headers, body
   preview, environment snapshot, and any additional context (for example the
   active workflow name).
4. Use the recorded context to verify which workflow or ingestion job triggered
   the error and collect the sanitized request payload for reproduction.

> **Where this comes from:** The middleware wraps each request, emits a
> structured debug report when responses are >=500 or when `include_client_errors`
> is enabled, and returns the `debug_report_id` to the caller when
> `response_on_error=True`. The report payload is produced by
> `build_debug_report`, which also records contextual fields for downstream
> correlation.【F:theo/infrastructure/api/app/debug/middleware.py†L20-L114】【F:theo/infrastructure/api/app/debug/reporting.py†L15-L188】

## 3. Follow the span and metrics trail

1. When a workflow is executed, the `instrument_workflow` context manager emits:
   - Structured `workflow.start` / `workflow.completed` log events with the same
     contextual attributes (request IDs, workflow names, durations, etc.).
   - OpenTelemetry spans annotated with the workflow metadata so that they show
     up in the console exporter or any OTLP backend you configure.
   - Prometheus metrics (`theo_workflow_runs_total` and
     `theo_workflow_latency_seconds`) labelled by workflow and status.
2. Use the Trace ID or workflow label from the debug report to filter spans and
   logs, and inspect the correlated metrics for regressions.
3. If you have the console tracer enabled locally, the span tree will include
   the workflow duration and any recorded exceptions, mirroring the log
   metadata.

> **Where this comes from:** The telemetry helpers wrap each workflow, attach
> serialised attributes to the active span, emit structured log records, and
> update the Prometheus counters/histograms before returning control to the
> caller.【F:theo/infrastructure/api/app/telemetry.py†L79-L207】

## 4. Trace into the database

1. Use the request metadata captured in the debug report (such as workflow name,
   document ID, or job ID) to find the associated records.
2. Common entry points:
   - `documents` and `passages` tables store ingested artifacts and the chunked
     text referenced in RAG responses.
   - `ingestion_jobs` records track asynchronous ingestion and enrichment tasks,
     including `document_id`, `job_type`, `status`, and timestamps for queueing
     and completion.
3. Query the database (for example with `psql`, `sqlite3`, or SQLAlchemy
   sessions) for the captured identifiers to inspect the persisted state and
   confirm whether retries or manual intervention are needed.
4. When investigating cache-related issues, also review the
   `theo_rag_cache_events_total` metric emitted by the telemetry helper to see
   whether reads were cache hits, misses, or refreshes.

> **Where this comes from:** The SQLAlchemy models define the document, passage,
> and ingestion job schemas that you can join against the context collected in
> the debug report, while the telemetry module emits cache metrics labelled by
> event status for deeper analysis.【F:theo/infrastructure/api/app/db/models.py†L1-L146】【F:theo/infrastructure/api/app/telemetry.py†L101-L214】

## 5. Recap

By carrying the `debug_report_id` (trace ID) from the UI into your log search
and telemetry tooling, you can pivot from a failed front-end action straight to
its API request metadata, correlated spans, Prometheus metrics, and finally the
database rows that record the canonical state. This end-to-end propagation is
now part of the default Theoria stack, so you can debug issues quickly
without having to reproduce them manually.
