> **Archived on 2025-10-26**

# Theoria — Final Build Spec (Standalone)

## 0) Mission & MVP

Goal: Build a research engine for theology that indexes your library (papers, notes, YouTube transcripts, audio), normalizes Scripture references (OSIS), and gives deterministic, verse-anchored search + a Verse Aggregator across the whole corpus.

MVP outcomes (no LLM required):

Ingest local files and URLs (including YouTube).

Parse to chunked, citation-preserving passages with page/time anchors.

Detect and normalize Bible references → OSIS.

Hybrid search (pgvector embeddings + lexical).

Verse Aggregator: open any OSIS (e.g., John.1.1) → see every snippet across the corpus, with jump links (page/time).

Minimal web UI: Upload, Search, Verse, Document.

Generative answers (RAG) are out of scope for MVP. Keep hooks ready for later.

> **Post-MVP extension:** See §18–§21 for the grounded generative copilot, export deliverables, batch enrichments, and topic monitoring layers that build on top of the MVP primitives.

## 1) Repo Layout (monorepo)

theo/
├─ services/
│  ├─ api/                 # FastAPI service
│  │  ├─ app/
│  │  │  ├─ main.py
│  │  │  ├─ routes/        # FastAPI routers
│  │  │  │  ├─ ingest.py
│  │  │  │  ├─ search.py
│  │  │  │  ├─ verses.py
│  │  │  │  └─ documents.py
│  │  │  ├─ core/          # db, settings, logging
│  │  │  ├─ ingest/        # parsers, chunkers, osis detection
│  │  │  ├─ retriever/     # hybrid search/rerank
│  │  │  ├─ models/        # pydantic schemas
│  │  │  └─ workers/       # Celery tasks
│  │  └─ requirements.txt
│  ├─ web/                 # Next.js 14 (App Router)
│  │  ├─ app/
│  │  │  ├─ upload/page.tsx
│  │  │  ├─ search/page.tsx
│  │  │  ├─ verse/[osis]/page.tsx
│  │  │  └─ doc/[id]/page.tsx
│  │  └─ package.json
│  └─ cli/                 # optional: bulk ingest CLI
│     └─ ingest_folder.py
├─ infra/
│  ├─ docker-compose.yml
│  ├─ db-init/pgvector.sql
│  └─ Makefile
├─ docs/
│  ├─ API.md
│  ├─ Chunking.md
│  ├─ OSIS.md
│  └─ Frontmatter.md
└─ .env.example

## 2) Stack

Backend: FastAPI (Python 3.11+), Celery workers, Redis broker.

DB: Postgres 15 with pgvector + pg_trgm.

Parsing: Docling (primary), Unstructured (fallback).

Bible refs: pythonbible for OSIS normalization.

Embeddings: BAAI/bge-m3 (1024-d) via sentence-transformers/FlagEmbedding.

Search: Hybrid = vector ANN (HNSW) + lexical (tsvector) with simple rerank.

Frontend: Next.js 14 (App Router), minimal pages.

## 3) Ingestion Types (standalone)

The engine accepts these source types out of the box. No extension/plugins required.

Articles / Papers: .pdf, .docx, .html, .txt

Web pages: canonical URL (fetch, sanitize to HTML/text)

YouTube: video URL (pull transcript if available; else queue ASR)

Audio: .mp3/.wav + optional transcript (.vtt/.srt/.json)

Markdown notes: .md with optional YAML frontmatter

Bibliography (optional): CSL-JSON for metadata backfill

If present, a small frontmatter JSON/YAML block improves provenance/dedupe (see §10).

### Ingestion Event Bus

Theo's ingestion pipeline emits structured events via `theo.platform.events.event_bus` so downstream systems can react without
polling. Two primary payloads are available:

* `DocumentIngestedEvent` – fired after a document is fully persisted (passages, storage artefacts, case objects). The default
  handlers log structured analytics entries and ensure the embedding backend is initialised for subsequent workloads.
* `CaseObjectsUpsertedEvent` – dispatched whenever Case Builder rows change. The API layer forwards these notifications to
  background workers (using Celery when available) so scoring, analytics, and other asynchronous jobs can run deterministically.

Handlers register once during API startup (`theo/services/api/app/events.py`). Custom services can subscribe to the same events to
enqueue bespoke processing or observability hooks without modifying the ingestion code paths.

## 4) Infrastructure

infra/docker-compose.yml
version: "3.9"
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: theo
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
    volumes: ["db:/var/lib/postgresql/data"]
  redis:
    image: redis:7
    ports: ["6379:6379"]
  api:
    build: ./services/api
    env_file: .env
    depends_on: [db, redis]
    ports: ["8000:8000"]
  web:
    build: ./services/web
    env_file: .env
    depends_on: [api]
    ports: ["3000:3000"]
volumes: { db: {} }

infra/db-init/pgvector.sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

.env.example
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/theo
REDIS_URL=redis://redis:6379/0
STORAGE_ROOT=/data
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
MAX_CHUNK_TOKENS=900
DOC_MAX_PAGES=5000
USER_AGENT="Theoria/1.0"

services/api/requirements.txt
fastapi[all]==0.115.*
uvicorn[standard]==0.30.*
psycopg[binary]==3.*
SQLAlchemy==2.*
pgvector==0.3.*
pydantic==2.*
python-multipart==0.0.*
celery==5.*
redis==5.*
docling==2.*            # primary parser
unstructured==0.15.*# fallback
pythonbible==0.1.*      # OSIS normalization
regex==2024.*
sentence-transformers==3.*
flagembedding==1.*# BGE-M3
beautifulsoup4==4.*     # web fetch cleanup
yt-dlp==2025.*# fetch YouTube metadata/transcript where allowed
youtube-transcript-api==0.6.*  # transcript fetcher
webvtt-py==0.5.*# parse VTT
pydub==0.25.*           # audio utils (metadata)

## 5) Database Schema (DDL)

-- documents: one row per source artifact (pdf, url, video, audio, note)
CREATE TABLE documents (
  id UUID PRIMARY KEY,
  title TEXT,
  authors TEXT[],
  source_url TEXT,
  source_type TEXT CHECK (source_type IN
    ('pdf','docx','html','txt','url','youtube','audio','markdown','note','ai_summary')),
  collection TEXT,
  pub_date DATE,
  channel TEXT,           -- for YouTube/podcasts
  video_id TEXT,          -- platform id
  duration_seconds INT,   -- if known
  bib_json JSONB,
  sha256 TEXT UNIQUE,
  storage_path TEXT,      -- path to original or normalized pack
  created_at TIMESTAMPTZ DEFAULT now()
);

-- passages: chunked spans with page or time anchors
CREATE TABLE passages (
  id UUID PRIMARY KEY,
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  page_no INT,            -- for paged docs
  t_start REAL,           -- seconds (for A/V)
  t_end REAL,             -- seconds (for A/V)
  start_char INT,
  end_char INT,
  osis_ref TEXT,          -- 'John.1.1-5' (nullable)
  text TEXT NOT NULL,
  tokens INT,
  embedding vector(1024),
  lexeme tsvector,
  meta JSONB              -- e.g., speaker, chapter title
);

CREATE INDEX ix_passages_embedding_hnsw ON passages USING hnsw (embedding vector_l2_ops);
CREATE INDEX ix_passages_lexeme ON passages USING gin (lexeme);
CREATE INDEX ix_passages_osis ON passages (osis_ref);
CREATE INDEX ix_passages_doc ON passages (document_id);

### Research reference datasets (seeded)

Theoria bundles a lightweight catalogue of verse-level tensions, harmonies, and commentary excerpts to keep the research panels deterministic in fresh deployments:

* `data/seeds/contradictions.json`, `data/seeds/contradictions_additional.json`, and `data/seeds/contradictions_catalog.yaml` populate the `contradiction_seeds` table. Entries are normalised to OSIS pairs and tagged with an explicit `perspective` (skeptical or apologetic) so the UI can filter skeptical critiques separately from harmonisation notes.
* `data/seeds/harmonies.yaml` and `data/seeds/harmonies_additional.yaml` feed the `harmony_seeds` table. These harmonies are tagged `apologetic` and surfaced alongside contradictions with toggleable filters in the reader.
* `data/seeds/commentaries.yaml` and `data/seeds/commentaries_additional.yaml` hydrate `commentary_excerpt_seeds`, exposing short-form commentary paragraphs keyed by OSIS and perspective. The `/research/commentaries` endpoint returns these records and supports perspective query parameters for the Commentaries panel.

Perspective-aware fetchers in the web app call `/research/contradictions` and `/research/commentaries` with one query parameter per selected perspective. When no perspective is selected the panels intentionally short-circuit, preventing misleading "no data" states.

All seed loaders live in `theo/services/api/app/db/seeds.py` and are idempotent; running them repeatedly keeps tables in sync with the bundled JSON/YAML without producing duplicates.

## 6) Chunking & Normalization (algorithms)

Document these in docs/Chunking.md & docs/OSIS.md. Implement in services/api/app/ingest/.

6.1 Parsing

Try Docling first. If it fails or yields empty content, fallback to Unstructured.

Preserve page numbers and element coordinates when available.

6.2 Chunking rules

Target ~900 tokens per chunk; clamp to 500–1200.

Respect block boundaries (headings, paragraphs, list items).

Don’t split a detected OSIS span across chunks if avoidable.

For PDFs, keep page_no for each chunk.

For transcripts:

Segment by sentence timestamps if provided; otherwise by caption blocks, coalesced up to ~40s window.

Keep t_start/t_end and a speaker field in meta when recognizable (SPEAKER: prefixes).

6.3 OSIS detection

Pass 1: regex on Bible book names + chapter:verse patterns (support English book aliases).

Pass 2: feed candidates into pythonbible to normalize to OSIS (Book.Chapter.Verse[-Chapter.Verse]).

If multiple refs appear, store:

osis_ref: minimal covering range,

meta.osis_refs_all: full list.

For ranges that overlap page/chunk boundaries, duplicate the OSIS on both chunks (it’s okay; Verse Aggregator dedupes later).

## 7) Embeddings & Hybrid Retrieval

7.1 Embeddings

Model: BAAI/bge-m3 (1024-d). Batch 64–128; L2 normalize.

Store in passages.embedding. Generate passages.lexeme via to_tsvector('english', text).

7.2 Candidate generation

If request includes osis: first select all passages whose osis_ref intersects query range (implement osis_intersects(a,b) in Python).

Else: gather top-K from vector index (cosine), union with top-K lexical (tsvector ranking/BM25-ish).

7.3 Rerank

Score = alpha *cosine_sim + (1 - alpha)* lexical_score (default alpha=0.65).

Boost passages with matching osis_ref when query includes verses even if text also present.

Deduplicate near-duplicates by same document_id and overlapping anchors.

## 8) API Contract

Document in docs/API.md. Implement in services/api/app/routes/.

8.1 Ingest

POST /ingest/file — multipart file (pdf, docx, html, txt, md, vtt, srt, json)
Optional frontmatter (JSON). Returns { document_id, status: "queued" }.

POST /ingest/url — JSON { url, source_type? }

URL ingest enforces scheme/host validation to avoid SSRF: only configured
schemes (default `http`/`https`) are accepted, localhost/RFC1918 hosts are
blocked, and additional CIDR or hostname rules can be tuned via the
`ingest_url_*` settings.

If YouTube: fetch metadata + transcript; create time-anchored passages.

If web page: fetch + sanitize → HTML→text.

POST /ingest/transcript — multipart: transcript (vtt/srt/json), optional audio (mp3/wav), optional frontmatter.

POST /jobs/reparse/{document_id} — enqueue re-ingestion.

8.2 Search

GET /search
Query params: q, osis?, author?, collection?, k?
Response:

{
  "query":"...","results":[
    {
      "document_id":"uuid","title":"...",
      "page_no":12,"t_start":123.4,"t_end":140.1,
      "osis_ref":"John.1.1-5","score":0.81,
      "snippet":"...logos was with God..."
    }
  ]
}

8.3 Verse Aggregator

GET /verses/{osis}/mentions
Returns all passages whose osis_ref intersects the requested ref/range, with anchors.

8.4 Documents

GET /documents/{id} — metadata + list of anchors
GET /documents/{id}/passages — paginated chunks with anchors

## 9) Web UI (Next.js 14)

/upload — upload file/URL; show job status.

/search — text box + filters (osis, author, collection). Results grouped by document; anchor links:

PDFs → ?page={page_no}#passage-{id}

A/V → ?t={t_start}s

/verse/[osis] — Verse Aggregator list of mentions; filters by source type/author.

/doc/[id] — simple reader with passages list and anchors.

Styling can be minimal (Tailwind optional). SSR fetch from API.

## 10) Frontmatter (optional but supported)

Accept as JSON (in form field frontmatter) or YAML at top of .md. Example fields:

id: "uuid-v4"
title: "Did Jesus Claim to Be God?"
source_type: "youtube"         # or "article" | "note" | "ai_summary" ...
authors: ["Ehrman, Bart D."]
channel: "Bart D. Ehrman"
video_id: "abc123"
date: "2021-03-14"
collection: "Christology/Debates"
tags: ["Ehrman","Divinity"]
osis_refs: ["John.1.1-5","Isa.52.13-53.12"]   # optional hints
sha256: "content hash"

## 11) Workers & Pipeline (outline code)

services/api/app/workers/tasks.py

```python
from celery import Celery
celery = Celery(__name__, broker="redis://redis:6379/0", backend="redis://redis:6379/0")

@celery.task(name="tasks.process_file")
def process_file(doc_id: str, path: str, frontmatter: dict = None):
    # parse -> chunk -> osis -> embed -> upsert

@celery.task(name="tasks.process_url")
def process_url(doc_id: str, url: str, source_type: str | None = None):
    # fetch web/youtube -> normalize -> chunk -> osis -> embed -> upsert
```

services/api/app/ingest/pipeline.py (key steps)

```python
def run_pipeline_for_file(doc_id, path, fm):
    # 1) detect type by extension; parse (Docling/Unstructured)
    # 2) chunk by rules (paged vs transcript)
    # 3) detect OSIS -> normalize
    # 4) embed (BGE-M3) -> upsert passages + lexeme

```

services/api/app/retriever/hybrid.py

```python
def search(q: str, osis: str | None, filters: dict, k: int):
    # 1) if osis: pull all OSIS-matching passages (range intersect)
    # 2) dense topK + lexical topK
    # 3) rerank & dedupe; return merged list

```

## 12) Definition of Done (MVP)

Ingest PDF and YouTube URL successfully → passages created with correct anchors.

/search works for:

keyword-only,

OSIS-only,

combined (keyword + OSIS).

/verses/{osis}/mentions returns correct list for seeded verse refs.

Web UI pages function (Upload/Search/Verse/Doc).

Basic persistence of originals + normalized JSON under STORAGE_ROOT/{document_id}/.

## 13) Testing & Fixtures

Fixtures:

fixtures/pdf/sample_article.pdf — contains a visible verse citation (e.g., “John 1:1–5”).

fixtures/youtube/transcript.vtt — with speaker tags and a verse mention.

fixtures/markdown/notes.md — with frontmatter + OSIS refs.

Tests:

Unit: OSIS regex → pythonbible normalization (edge cases: ranges, multiple refs).

Integration: ingest PDF → search by q=logos osis=John.1.1-5 returns expected doc/page.

Verse aggregator: GET /verses/John.1.1/mentions lists ≥1 passage with correct anchors.

## 14) Make Targets

infra/Makefile

up:      ## start all services
\tdocker compose up --build -d
down:
\tdocker compose down
migrate: ## install extensions
\tdocker compose exec -T db psql -U postgres -d theo < infra/db-init/pgvector.sql
logs:
\tdocker compose logs -f api web
psql:
\tdocker compose exec db psql -U postgres -d theo

## 15) Non-Goals (MVP) & Hooks for Next Sprint

Not in MVP: RAG answerer, text-reuse graphs, CollateX alignment, IIIF viewer, OpenAlex/GROBID enrichment, auth/multi-tenant, fine-grained permissions.

Keep hooks:

passages.meta for future speaker, chapter, osis_refs_all.

Worker queue for passim/CollateX tasks.

documents.bib_json for later OpenAlex/GROBID enrichment.

## 16) Post-MVP Roadmap (toggle-able)

Text-reuse: passim over corpus → “Parallels” sidebar.

Alignment: CollateX diff view between selected passages.

RAG answers: small open-weights model via vLLM (Qwen2.5-32B / Llama-3.1-70B / Mixtral). Strict citation policy: answer only from retrieved passages.

Metadata enrich: GROBID + OpenAlex; DOI/venue backfill.

IIIF pane: render scanned plates next to normalized text.

Auth + collections: user orgs; per-collection indices.

## 17) Notes & Guardrails

Always store originals and normalized JSON under STORAGE_ROOT/{document_id} for reproducibility.

Record parser, parser_version, chunker_version in passages.meta.

Keep embeddings L2-normalized; consistent preprocessing (lowercase/strip) before tsvector.

Implement a robust range-intersect for OSIS to avoid false misses.

Respect robots/ToS for URL/YouTube fetching; cache transcripts; expose a manual “upload transcript” path.

## 18) AI Copilot Layer (ChatGPT 5-ready)

The MVP hooks now power a grounded generative layer that stays tethered to Theo’s corpus.

### 18.1) Provider & Model Registry

- **Settings store:** Extend `core/settings.py` with a persistent `ai_providers` map stored in Postgres (`settings` table) and cached in Redis. Keys: `provider`, `api_key`, `base_url`, `default_model`, `extra_headers`.
- **Supported providers:** OpenAI, Azure OpenAI, Anthropic, Google Vertex adapters, local vLLM endpoints. Provider schemas inherit from a `BaseProviderSettings` Pydantic model.
- **Model catalog:** `/settings/ai/models` endpoint allows admins to register named presets, e.g. `"gpt-4o-mini@openai"` → provider, model id, max output tokens, citation guardrails (boolean), cost metadata.
- **Key rotation:** Settings API supports PUT/PATCH to rotate keys. Keys are encrypted at rest via Fernet using `SETTINGS_SECRET_KEY`.

### 18.2) Guarded Response Flow

- **Pipeline:** Request → Retrieve passages (hybrid search) → Build prompt (system instructions enforce OSIS citations) → Invoke selected model → Validate citations.
- **Citation validator:** Every answer must include at least one OSIS reference per claim. Validator checks that referenced OSIS ranges exist in the retrieved bundle and that passage anchors (page/time offsets) are present. Responses without support are rejected with a 422 and logged for review.
- **Caching:** Responses are stored in Redis with a composite key (`user`, `prompt_hash`, `model_preset`, `retrieval_hash`).

### 18.3) Chat Surfaces & Use Cases

All generative entry points share the same grounding policies but tailor prompt templates to the workflow. ChatGPT 5 can be swapped for any registered provider/model.

1. **Verse-Linked Research Copilot** – Highlight a verse in the Verse Aggregator to receive a synthesis citing every relevant passage, with follow-up prompts that pivot across patristic vs. contemporary commentary.
2. **Context-Aware Sermon/Teaching Prep** – Summarize packeted sources into outlines, liturgy elements, reflection questions, respecting denominational guardrails supplied via filters and metadata.
3. **Scholarly Comparative Analysis** – Compare authors (e.g., Augustine vs. Calvin vs. Barth on Romans 8) with answers linking to each source and auto-generating CSL-JSON bibliography stubs stored as `ai_summary` documents.
4. **Multimedia Insight Extraction** – Derive timecoded Q&A digests, highlight reels, and cross-modal “study packs” by pairing podcast snippets with related PDFs.
5. **Guided Personal Devotion & Discipleship** – Craft daily devotionals, prayers, and catechesis flows that cite OSIS verses and honour doctrinal constraints.
6. **Corpus Maintenance & Curation Assistant** – Auto-summarize new ingests, flag duplicates via SHA-256, suggest metadata normalizations, and translate Celery/Redis status into natural-language admin digests.
7. **Research Collaboration Layer** – Support shared annotations, consensus drafts, and change summaries when new documents land, all grounded in the authoritative sources.
8. **Export-Oriented Deliverables Assistant** – From any chat, let users trigger export jobs (Markdown, NDJSON, CSV) bundling cited passages into sermon packets or Q&A digests with manifest metadata for reproducibility.

### 18.4) API Surface

- `POST /ai/chat`: accepts `model_preset`, `messages`, optional `retrieval_filters`. Requires the client to select from registered presets.
- `GET /ai/models`: lists available presets with cost/tokens metadata.
- `PUT /settings/ai/providers/{provider}`: upserts credentials. Only accessible to admin roles.
- All responses include `citations` array (`osis`, `document_id`, `anchor_type`, `anchor_value`).

### 18.5) Guardrailed Conversation Pipeline

- **Retrieval-first loop:** Every user turn first calls the hybrid retriever. Generation prompts are constructed solely from the retrieved passages plus system rails that enforce OSIS citations and anchor metadata.
- **Refusal path:** If retrieval returns no eligible support, the rail layer short-circuits generation and sends a refusal template explaining the lack of grounded sources.
- **Rail stack:** Adopt a policy framework such as NeMo Guardrails to encode prompt-injection filters, tool-use allowlists, and output sanitization aligned with OWASP LLM Top-10 mitigations.

### 18.6) Citation Audit & Cache

- **Justification record:** Persist `{conversation_id, turn_id, passage_ids, osis_ranges, retrieval_hash}` for each response so auditors can replay support.
- **Nightly verifier:** Schedule a Celery job that re-scores cached answers against the latest embeddings and flags low-faithfulness items in an admin dashboard.
- **Warm cache:** Supported answers are cached in Redis keyed by the justification record, allowing identical queries to reuse previously validated content.

### 18.7) Workflow Panels

- **Prompt presets:** Ship eight prompt/config panels (the roles above) that pre-select filters like author, era, and source type while pinning expected output formats (Markdown, NDJSON, CSV).
- **UI wiring:** Panels live in the chatbot sidebar; selecting one seeds the system message, retrieval filters, and export hooks so users can run reproducible, OSIS-grounded workflows in a click.

### 18.8) Provider Orchestration & Budgets

- **Router service:** Introduce a lightweight router that maps task classes (summarization, comparative analysis, devotional drafting) to registered model presets and enforces latency/cost ceilings.
- **Budget handling:** When projected spend exceeds limits, degrade gracefully by switching to faster presets or shortening responses, keeping guardrails active regardless of fallback.

### 18.9) Telemetry & Red-Team Harness

- **Metrics:** Instrument per-workflow telemetry for retrieval coverage, citation validation rates, refusals, and cache hits, storing aggregates in ClickHouse or Postgres for dashboarding.
- **Red-team suite:** Maintain a prompt collection focused on OWASP LLM risks (prompt injection, insecure outputs, excessive autonomy). Run it in CI and on a schedule to evaluate guardrail effectiveness.

## 19) Export-Ready Deliverables

Sermon/lesson prep and Q&A transcripts now surface export pipelines.

- **Formats:** Markdown (teaching outline + citations), NDJSON (one item per segment with provenance), CSV (tabular Q&A with OSIS refs).
- **Manifest:** Each export includes `manifest.json` with `export_id` (ULID), `schema_version`, `filters`, `git_sha`, `generated_at`, and `model_preset` when AI content is present.
- **API:** `POST /export/deliverable` accepts `{ "type": "sermon" | "qa", "source_ids": [], "model_preset": "...", "format": ["markdown","ndjson","csv"] }` and returns signed URLs. Jobs run via Celery, writing assets under `STORAGE_ROOT/exports/{export_id}/`.
- **UI Hooks:** Verse Aggregator and document detail pages expose “Export sermon packet” and “Export Q&A digest” buttons that queue the Celery job and notify the user when ready.

## 20) CLI Batch Intelligence

Extend `theo.services.cli.ingest_folder` with a `--post-batch` flag to trigger enrichers immediately after ingest:

- `summaries` – calls `/ai/chat` with the “Corpus Maintenance” prompt to create `ai_summary` documents stored alongside originals.
- `tags` – hits the metadata enrichment endpoint to refresh topics/subjects.
- `biblio` – generates CSL-JSON stubs when missing and persists them via `documents/{id}/bibliography`.

The CLI writes enrichments back into the corpus using the API, logging each export manifest path. Batch jobs respect the same citation guardrails as interactive chats.

## 21) Automated Alerts & Topic Monitoring

- **OpenAlex integration:** After each ingest window, run `jobs/topic_digest` Celery task. It fetches OpenAlex topics for new documents (via DOI/title lookup) and clusters passages by `primary_topic` + top-N topics.
- **Under-represented themes:** The job identifies topics whose document count increased this week or remain below a configured threshold and emits a digest summary.
- **Delivery:** Weekly digests are emailed/slacked to admins and stored as `digest` documents with links to the underlying passages and exports.
- **Dashboard:** `/admin/digests` UI lists digests, cluster stats, and quick actions to start AI analyses using the registered model presets.

## 22) Grounded RAG Guardrails

- **Mandatory citations:** All AI-generated text must include OSIS references with anchors. Missing citations cause the response to be rejected and the model output stored for debugging.
- **Source packet limitation:** Prompts include only the retrieved passages. The application never permits free-form generations.
- **Evaluation:** Nightly Celery task `jobs/validate_citations` replays a sample of conversations, checking citation integrity and logging drift.
- **Audit trail:** Responses store `retrieval_snapshot` (passage IDs, embeddings hash) to make exports reproducible and auditable.

## 23) Vector Search Tune-Up

- **ANN acceleration:** Enable pgvector’s HNSW indexes on passage embeddings to speed hybrid retrieval bursts triggered by the conversation pipeline.
- **Maintenance tasks:** Add a weekly `jobs/refresh_hnsw` task that rebuilds indexes after large ingests and tracks recall metrics against a held-out validation set.
- **Observability:** Record HNSW latency/recall metrics alongside the telemetry stack so regressions surface in the AI copilot dashboards.
