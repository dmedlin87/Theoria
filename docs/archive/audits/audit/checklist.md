# Theoria Audit Checklist

## Frontend

- [x] FE1 – Initialise `mode` via `useMode()` inside `app/copilot/page.tsx`. 【F:theo/services/web/app/copilot/page.tsx†L154-L190】
- [x] FE2 – Define `handleCitationExport` and compute `citations` before quick-start export. 【F:theo/services/web/app/copilot/page.tsx†L383-L442】
- [x] FE3 – Close the sermon rendering block so outline/key points only render for sermon results. 【F:theo/services/web/app/copilot/components/WorkflowResultPanel.tsx†L41-L70】
- [x] FE4 – Align research mode payload with backend (`model` vs `mode`). 【F:theo/services/web/app/copilot/page.tsx†L259-L308】【F:theo/services/api/app/models/ai.py†L236-L256】

## Backend

- [x] API1 – Allow missing `source_url` when exporting citations. 【F:theo/services/api/app/ai/rag/models.py†L12-L45】
- [x] API2 – Import `Iterable` in `ai/rag` guardrails to stop guardrail crashes. 【F:theo/services/api/app/ai/rag/guardrails.py†L1-L38】
- [x] API3 – Accept/translate the frontend’s research mode selection. 【F:theo/services/api/app/models/ai.py†L236-L308】
- [x] ING1 – Sanitize file upload paths in `/ingest/file`. 【F:theo/services/api/app/routes/ingest.py†L43-L156】
- [x] ING2 – Sanitize transcript/audio filenames in `/ingest/transcript`. 【F:theo/services/api/app/routes/ingest.py†L333-L390】
- [x] ING3 – Restrict URL ingestion to safe schemes/hosts and enforce timeouts. 【F:theo/services/api/app/ingest/network.py†L97-L220】【F:theo/services/api/app/ingest/pipeline.py†L74-L93】
- [x] ING4 – Stream large uploads and enforce size limits. 【F:theo/services/api/app/routes/ingest.py†L85-L156】【F:theo/services/api/app/routes/ingest.py†L333-L375】

## Infra / Security

- [x] Confirm SSRF/LFI mitigations and path traversal fixes are deployed across environments. 【F:theo/services/api/app/routes/ingest.py†L43-L390】【F:theo/services/api/app/ingest/network.py†L97-L236】
