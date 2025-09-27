# TheoEngine Code Audit Report

## Executive Summary
1. **Copilot page crashes because `mode` is never initialised** – the page uses `mode.id` in every workflow request without ever calling `useMode()`, causing an immediate runtime ReferenceError and blocking the entire feature. 【F:theo/services/web/app/copilot/page.tsx†L451-L517】【0d1eb1†L1-L36】
2. **Citation quick-start flow references undefined symbols** – `handleQuickStart` posts `citations` and `mode` values that are not defined in scope, so presets and citation exports consistently throw. 【F:theo/services/web/app/copilot/page.tsx†L635-L692】【0d1eb1†L37-L66】
3. **Sermon result rendering leaks outside its guard** – missing braces leave `result.payload.outline/key_points` executing for every result kind, leading to `.map` on `undefined` and hard crashes for non-sermon workflows. 【F:theo/services/web/app/copilot/page.tsx†L1193-L1311】【0d1eb1†L21-L38】
4. **Citation export endpoint rejects valid payloads** – the API requires `source_url` on `RAGCitation`, returning 422s for requests without it, contradicting the tests and the frontend contract. 【F:theo/services/api/app/ai/rag.py†L147-L156】【c0c158†L1-L25】
5. **Guardrail filter throws NameError** – `_extract_topic_domains` uses `Iterable` without importing it, so any guarded answer path fails at runtime. 【F:theo/services/api/app/ai/rag.py†L56-L70】【40ec00†L1-L41】
6. **Research mode never reaches the backend** – the frontend sends a `mode` field, but every FastAPI schema expects `model`, so mode toggles silently do nothing. 【F:theo/services/web/app/copilot/page.tsx†L451-L512】【F:theo/services/api/app/models/ai.py†L179-L210】
7. **File ingestion allows path traversal writes** – combining `tmp_dir / file.filename` lets filenames like `../evil.py` escape the sandbox, enabling arbitrary file writes. 【F:theo/services/api/app/routes/ingest.py†L36-L65】
8. **Transcript ingestion repeats the traversal flaw for both transcript and audio uploads** – crafted filenames can overwrite files outside the temp directory. 【F:theo/services/api/app/routes/ingest.py†L88-L135】
9. **URL ingestion enables SSRF/LFI** – `_fetch_web_document` blindly `urlopen`s attacker-controlled URLs (including `file://` or internal hosts) with no allow-list or timeout. 【F:theo/services/api/app/ingest/pipeline.py†L790-L809】
10. **Ingestion endpoints read entire uploads into memory** – `await file.read()` on unbounded files (and transcripts/audio) permits easy memory exhaustion. 【F:theo/services/api/app/routes/ingest.py†L44-L48】【F:theo/services/api/app/routes/ingest.py†L102-L112】

### Risk Heatmap

| Subsystem | Critical | High | Medium | Low |
|-----------|----------|------|--------|-----|
| Frontend / Next.js | 1 | 2 | 0 | 0 |
| API / FastAPI | 2 | 1 | 0 | 0 |
| Workers / Celery | 0 | 0 | 0 | 0 |
| DB / Models | 0 | 0 | 0 | 0 |
| Search / Indexing | 0 | 0 | 0 | 0 |
| OSIS Utilities | 0 | 0 | 0 | 0 |
| Ingestion / Transcripts | 3 | 0 | 1 | 0 |

## Findings by Subsystem

### Frontend / Next.js

| Issue ID | File & Line | Severity | Category | Repro Steps | Suggested Fix |
|----------|-------------|----------|----------|-------------|---------------|
| FE1 | `app/copilot/page.tsx` L451-L517 | Critical | Functional bug | Load Copilot, submit any workflow → ReferenceError for `mode`. | Call `const { mode } = useMode()` (and `modes` if needed) near the top of the component. Guard API payloads accordingly. 【F:theo/services/web/app/copilot/page.tsx†L451-L517】【0d1eb1†L1-L36】 |
| FE2 | `app/copilot/page.tsx` L635-L692, L1193-L1323 | High | Functional bug | Click a quick-start preset → fetch body references undefined `citations`; export buttons reference `handleCitationExport`. | Introduce `const handleCitationExport = (...) => { ... }` and derive `const citations = result?.payload?.answer.citations ?? []` (with proper null checks) before use. 【F:theo/services/web/app/copilot/page.tsx†L635-L692】【F:theo/services/web/app/copilot/page.tsx†L1193-L1323】【0d1eb1†L37-L66】 |
| FE3 | `app/copilot/page.tsx` L1193-L1311 | High | Functional bug | Run a non-sermon workflow → render path executes `result.payload.outline.map`, throwing because `outline` is undefined. | Close the sermon block before the next condition (`)}`) so that outline/key-points only render for `kind === "sermon"`. Add optional chaining. 【F:theo/services/web/app/copilot/page.tsx†L1193-L1311】【0d1eb1†L21-L38】 |
| FE4 | `app/copilot/page.tsx` L451-L512 | High | Schema mismatch | Toggle research mode and run a workflow – backend receives `mode`, ignores it, and defaults the model. | Rename payload field to `model` (matching FastAPI schema) or add a backend alias; map `mode.id` → allowed model string before POST. 【F:theo/services/web/app/copilot/page.tsx†L451-L512】【F:theo/services/api/app/models/ai.py†L179-L210】 |

### API / FastAPI

| Issue ID | File & Line | Severity | Category | Repro Steps | Suggested Fix |
|----------|-------------|----------|----------|-------------|---------------|
| API1 | `ai/rag.py` L147-L156 | Critical | Schema mismatch | POST `/ai/citations/export` without `source_url` (per tests) → 422. | Make `source_url` optional (`str | None`) and default missing values; adjust validation & CSL builder to handle `None`. 【F:theo/services/api/app/ai/rag.py†L147-L156】【c0c158†L1-L25】 |
| API2 | `ai/rag.py` L56-L70 | Critical | Functional bug | Call any guarded answer path (e.g., `/ai/multimedia`) → NameError for `Iterable`. | Import `Iterable` from `collections.abc`/`typing` and unit-test `_extract_topic_domains`. 【F:theo/services/api/app/ai/rag.py†L56-L70】【40ec00†L1-L41】 |
| API3 | `ai/models.py` L179-L210 | High | Schema mismatch | Observe frontend sending `mode` while schemas expect `model`; backend never sees mode preference. | Accept `mode` as alias via `Field(validation_alias=...)` or update frontend to send `model`. Document allowed values. 【F:theo/services/api/app/models/ai.py†L179-L210】【F:theo/services/web/app/copilot/page.tsx†L451-L512】 |

### Workers / Celery

| Issue ID | Status | Severity | Notes |
|----------|--------|----------|-------|
| – | Needs Human Review | – | No worker-specific code paths were exercised in this pass; please review retry/idempotency manually. |

### DB / Models

| Issue ID | Status | Severity | Notes |
|----------|--------|----------|-------|
| – | Needs Human Review | – | No schema-level issues observed during this slice; confirm migrations/indexes align with queries. |

### Search / Indexing

| Issue ID | Status | Severity | Notes |
|----------|--------|----------|-------|
| – | Needs Human Review | – | Vector/BM25 configuration not assessed in this pass. |

### OSIS Utilities

| Issue ID | Status | Severity | Notes |
|----------|--------|----------|-------|
| – | Needs Human Review | – | OSIS parsing & expansion logic not exercised; targeted tests recommended. |

### Ingestion / Transcripts

| Issue ID | File & Line | Severity | Category | Repro Steps | Suggested Fix |
|----------|-------------|----------|----------|-------------|---------------|
| ING1 | `routes/ingest.py` L36-L65 | Critical | Security (Path traversal) | Upload a file named `../pwn.txt`; server writes outside temp dir. | Sanitize filenames (`Path(file.filename).name`), write via `NamedTemporaryFile(delete=False)`, and never trust client filenames. 【F:theo/services/api/app/routes/ingest.py†L36-L65】 |
| ING2 | `routes/ingest.py` L88-L135 | Critical | Security (Path traversal) | Same attack via transcript/audio upload names. | Apply the same sanitisation and random naming for transcript/audio artifacts. 【F:theo/services/api/app/routes/ingest.py†L88-L135】 |
| ING3 | `ingest/pipeline.py` L790-L809 | Critical | Security (SSRF/LFI) | POST `/ingest/url` with `file:///etc/passwd` or internal host – backend fetches it. | Restrict schemes to `http/https`, enforce allow-lists, add DNS rebinding protections, and pass explicit timeouts to `urlopen`. 【F:theo/services/api/app/ingest/pipeline.py†L790-L809】 |
| ING4 | `routes/ingest.py` L44-L48, L102-L112 | Medium | Reliability | Upload multi-GB file → process reads entire payload into memory. | Stream uploads to disk in chunks, enforce Content-Length limits, and reject oversize files early. 【F:theo/services/api/app/routes/ingest.py†L44-L48】【F:theo/services/api/app/routes/ingest.py†L102-L112】 |

## Quick Wins (≤ 1 hour)
- Import `Iterable` and add a guardrail unit test to unblock guardrail-powered endpoints. 【F:theo/services/api/app/ai/rag.py†L56-L70】【40ec00†L1-L41】
- Make `source_url` optional in `RAGCitation` so citation exports stop returning 422s. 【F:theo/services/api/app/ai/rag.py†L147-L156】【c0c158†L1-L25】
- Sanitize upload filenames by using `Path(name).name` and random prefixes before writing to disk. 【F:theo/services/api/app/routes/ingest.py†L36-L65】【F:theo/services/api/app/routes/ingest.py†L88-L135】

## Stability First (Critical Correctness)
- Restore `useMode()` wiring and correct JSX blocks so Copilot workflows work without crashing. 【F:theo/services/web/app/copilot/page.tsx†L451-L517】【F:theo/services/web/app/copilot/page.tsx†L1193-L1311】
- Lock down ingestion URL handling (scheme allow-list + timeout) to prevent SSRF/LFI. 【F:theo/services/api/app/ingest/pipeline.py†L790-L809】
- Address path traversal in every ingestion entrypoint before accepting untrusted uploads. 【F:theo/services/api/app/routes/ingest.py†L36-L135】
