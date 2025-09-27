# TheoEngine Audit Checklist

## Frontend
- [ ] FE1 – Initialise `mode` via `useMode()` inside `app/copilot/page.tsx`. 【F:theo/services/web/app/copilot/page.tsx†L451-L517】
- [ ] FE2 – Define `handleCitationExport` and compute `citations` before quick-start export. 【F:theo/services/web/app/copilot/page.tsx†L635-L692】【F:theo/services/web/app/copilot/page.tsx†L1193-L1323】
- [ ] FE3 – Close the sermon rendering block so outline/key points only render for sermon results. 【F:theo/services/web/app/copilot/page.tsx†L1193-L1311】
- [ ] FE4 – Align research mode payload with backend (`model` vs `mode`). 【F:theo/services/web/app/copilot/page.tsx†L451-L512】【F:theo/services/api/app/models/ai.py†L179-L210】

## Backend
- [ ] API1 – Allow missing `source_url` when exporting citations. 【F:theo/services/api/app/ai/rag.py†L147-L156】
- [ ] API2 – Import `Iterable` in `ai/rag.py` to stop guardrail crashes. 【F:theo/services/api/app/ai/rag.py†L56-L70】
- [ ] API3 – Accept/translate the frontend’s research mode selection. 【F:theo/services/api/app/models/ai.py†L179-L210】
- [ ] ING1 – Sanitize file upload paths in `/ingest/file`. 【F:theo/services/api/app/routes/ingest.py†L36-L65】
- [ ] ING2 – Sanitize transcript/audio filenames in `/ingest/transcript`. 【F:theo/services/api/app/routes/ingest.py†L88-L135】
- [ ] ING3 – Restrict URL ingestion to safe schemes/hosts and enforce timeouts. 【F:theo/services/api/app/ingest/pipeline.py†L790-L809】
- [ ] ING4 – Stream large uploads and enforce size limits. 【F:theo/services/api/app/routes/ingest.py†L44-L48】【F:theo/services/api/app/routes/ingest.py†L102-L112】

## Infra / Security
- [ ] Confirm SSRF/LFI mitigations and path traversal fixes are deployed across environments. 【F:theo/services/api/app/routes/ingest.py†L36-L135】【F:theo/services/api/app/ingest/pipeline.py†L790-L809】
