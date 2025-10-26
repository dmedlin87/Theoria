> **Archived on 2025-10-26**

# Theoria: Deep-Research Bible Reader & Critical Analysis Agent

**Goal.** A verse-first Bible reader that turns every passage into a research workspace: textual variants, cross-references, morphology, historical context, contradiction/harmony checks, apologetic vs. skeptical notes, and citable evidence on tap while you read.

**Why this approach.** Open biblical corpora (OSIS references, open translations and morphology datasets), cross-reference and geocoding datasets, and open scholarly indexes (e.g., OpenAlex/Crossref) now make a serious research UX feasible. The agent stays retrieval-grounded, runs short planning steps, calls tools for deterministic data, and only then writes analysis with citations.

---

## 1) Product pillars

1. **Reader + Research Dock** (verse-anchored)
   - Chips per verse/selection open panels: **Cross-References**, **Textual Variants**, **Morph & Interlinear**, **Historical Context**, **Contradictions & Harmonies**, **Commentaries & Perspectives**, and **Living Study Notes**.
   - Split view: pin any two passages with synchronized scrolling and highlight parallels.
   - Command palette: "Compare translations", "Open contradictions", "Search papers", "Show DSS links", etc.

2. **Agentic analysis (plan → tool calls → report)**
   - ReAct-style short plan → retrieval/comparison tools → two-column summary (Apologetic vs Skeptical) with footnotes.
   - Always "tools first, generation second" for auditability.

3. **Living Notes (gets smarter as you study)**
   - Structured **Claim Cards** (type/stance/confidence) + **Evidence Cards** (citations). Reuse raises a source's credibility weight across the app.

4. **Licensing-aware content**
   - Prefer open corpora first (e.g., SBLGNT licensing, MorphGNT, OSHB). Clearly badge licenses in the UI and respect redistribution limits for modern study notes (e.g., NET notes).

5. **Creator & Media Profiles**
   - First-class ingestion and retrieval over user-provided media transcripts (e.g., YouTube). Build creator/topic stances with time-coded quotes, link segments to OSIS verses, and surface them inline in the reader and Deep-Dive reports.

---

## 2) Core datasets & libraries (starter set)

- **OSIS** (canonical verse IDs): all notes, claims, and citations are keyed to OSIS (e.g., `Luke.2.1`), making them portable across translations.
- **Bible modules**: SWORD/JSword modules for public translations and dictionaries (OSIS/TEI/ThML).
- **Greek (NT)**: SBLGNT text + MorphGNT morphology (merge server-side; observe licenses).
- **Hebrew (OT)**: OSHB (text + morphology) and allied lexica where permissible.
- **Cross-references**: Open datasets (e.g., TSK-style / OpenBible cross-refs). 
- **Geocoding**: Open Bible atlas/places datasets with confidence scores.
- **Scholarly discovery**: OpenAlex and Crossref APIs for papers/books (store IDs, DOIs, titles, venues, years).
- **Dead Sea Scrolls links**: outward links to authoritative collections for relevant verses.
- **Contradiction seeds**: community datasets (e.g., SAB/BibViz) clearly labeled as non-peer-reviewed; balance with apologetic harmonizations.

> All external datasets should be cached with provenance and licensing metadata. Show license badges per panel; block export of restricted content.

---

## 3) UX blueprint (reader-first, research instant)

**Layout**
- **Top bar**: translation dropdown, search, **Mode** toggle (Neutral / Skeptical / Apologetic), "Deep-Dive" button.
- **Reader** (center): OSIS-anchored text; verse numbers show hover badge with quick actions.
- **Research Dock** (right): chips expand into panels.
- **Split view**: pin two passages (e.g., Luke 2 vs Matt 2), sync scroll.

**Panels**
- **Cross-References** - ranked graph of related verses; open side-by-side.
- **Textual Variants** - base text, major variants; translation diffs; apparatus notes where available.
- **Morph & Interlinear** - lemma, parsing, glosses.
- **Historical Context** - timeline card (who/when/where), brief summaries, links to external sources; show DSS links when relevant.
- **Contradictions & Harmonies** - known entries with citations, plus user/vetted notes.
- **Commentaries & Perspectives** - tabs for "Apologetic" vs "Critical" (e.g., Bart D. Ehrman) with side-by-side arguments, now
  backed by cached creator verse rollups so quotes and stance summaries load instantly when a verse chip is opened.
- **Study Notes (Living)** - your structured notes: claims, fallacies flagged, verdicts, sources; all OSIS-anchored.

**Ergonomics**
- Hover actions on verse numbers; inline highlights where cross-refs or variants exist.
- Command palette: one-keystroke to open panels/actions.
- One-click **Deep-Dive**: runs the agent workflow and opens a printable, citable report.
- **Creators chip (per verse):** shows a badge when any transcript segment mentions the verse; opens a list of time-coded quotes and links to the video timestamp.
- **Search bar shortcuts:** e.g., "Wes Huff on baptism" → Creator Topic page with stance summary, top quotes, and linked verses.
- **Creator Profile pages:** topic cloud, stance summaries, recent videos; quotes are copyable with timestamped links and OSIS anchors.

---

## 4) Tool catalog (JSON schemas)

> Keep a small, typed set of tools (<15). Deterministic outputs; runtime validates arguments.

### 4.1 `scripture_retrieve`
```json
{
  "name": "scripture_retrieve",
  "description": "Fetch verses by OSIS, translation(s), optional range, with verse metadata.",
  "parameters": {
    "type": "object",
    "properties": {
      "osis": {"type":"string","description":"e.g., 'Luke.2.1-Luke.2.7'"},
      "translations": {"type":"array","items":{"type":"string"}},
      "include_meta": {"type":"boolean","default": true}
    },
    "required": ["osis"]
  }
}
```

### 4.2 `crossrefs_lookup`
```json
{
  "name": "crossrefs_lookup",
  "description": "Return ranked cross-references for a verse or range.",
  "parameters": {
    "type":"object",
    "properties":{"osis":{"type":"string"},"limit":{"type":"integer","default":50}},
    "required":["osis"]
  }
}
```

### 4.3 `variants_apparatus`
```json
{
  "name":"variants_apparatus",
  "description":"Return variant readings/notes for a verse (NT=Greek; OT=Hebrew) and major translation diffs.",
  "parameters":{"type":"object","properties":{"osis":{"type":"string"}}, "required":["osis"]}
}
```

### 4.4 `historicity_search`
```json
{
  "name":"historicity_search",
  "description":"Query scholarly indexes for works related to a claim/person/place; return compact citations.",
  "parameters":{"type":"object","properties":{
    "query":{"type":"string"},
    "year_from":{"type":"integer"},
    "year_to":{"type":"integer"},
    "limit":{"type":"integer","default":20}
  }, "required":["query"]}
}
```

### 4.5 `geo_places`
```json
{
  "name":"geo_places",
  "description":"Look up biblical places and coordinates with confidence.",
  "parameters":{"type":"object","properties":{"place":{"type":"string"}},"required":["place"]}
}
```

### 4.6 `contradiction_index`
```json
{
  "name":"contradiction_index",
  "description":"Search seeded contradictions/harmonies by OSIS or topic.",
  "parameters":{"type":"object","properties":{
    "osis":{"type":"string"},
    "topic":{"type":"string"},
    "limit":{"type":"integer","default":25}
  }}
}
```

### 4.7 `fallacy_detect`
```json
{
  "name":"fallacy_detect",
  "description":"Label likely logical fallacies/persuasion techniques in text.",
  "parameters":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}
}
```

### 4.8 `report_build`
```json
{
  "name":"report_build",
  "description":"Assemble retrieved passages, notes, and citations into a printable MD/HTML report.",
  "parameters":{"type":"object","properties":{
    "title":{"type":"string"},
    "sections":{"type":"array","items":{"type":"object"}},
    "export":{"type":"string","enum":["md","html","pdf"],"default":"md"}
  }, "required":["title","sections"]}
}
```

---

## 5) Agent workflows

### A) Passage Deep-Dive
**Prompt**: "Deep-dive Luke 2:1-7; show contradictions vs harmonies; add history on Quirinius/Herod."  
**Plan**: `scripture_retrieve` → `crossrefs_lookup` → `variants_apparatus` → `historicity_search` → `contradiction_index` → `report_build` (Apologetic vs Critical, footnoted).

### B) Fallacy Audit (argument paragraph)
Segment claims → `fallacy_detect` → check premises via `scripture_retrieve`/`variants_apparatus` → report with labels & receipts.

### C) Geo-Temporal Sanity Check
Extract names/dates/places → `geo_places` + timeline overlay → flag infeasible legs; annotate assumptions.

**Creator sync into Living Notes**
1) On ingestion, segment text is scanned for Bible refs and topics; OSIS anchors and tags are saved on `transcript_segments`.
2) As users ask "What does <Creator> think about <Topic>?", hybrid search retrieves segments; the agent proposes or updates `creator_claims` (stance + claim_md + confidence).
3) When a claim is accepted, the app creates/updates a `note` (stance=apologetic|critical|neutral, claim_type=doctrinal|historical|textual|logical) and adds `evidence` rows that point to `transcript_quotes` with timestamped `source_ref`.
4) Deep-Dive reports include these quotes automatically in the Evidence list for the relevant verses/topics.

---

## Research Trails & Auditability

**Why:** Make every deep-dive reproducible and reviewable.

**Scope**
- Persist an *Agent Trail* object per run: prompt mode, plan, ordered tool calls (name + validated args), tool outputs digests, final answer, citations, and versioned references to datasets used.
- Allow "replay with updates" to re-run the same trail against newer modules/datasets.

**Schema additions (conceptual)**
- `agent_trails (id, created_at, user_id, mode, plan_md, final_md)`
- `agent_steps (trail_id, step_index, tool, args_json, output_digest, tokens_in, tokens_out)`
- `trail_sources (trail_id, source_type, ref)`

**API**
- `GET /api/trails/:id`  → return full trail for audit
- `POST /api/trails/:id/replay` → run the same plan with current data; mark diffs

**Acceptance**
- From a Deep-Dive, user can open the trail, see steps, tool args, source IDs, and costs; can replay and compare outputs.

---

## 6) Data model (starter, Postgres)

### 6.1 `notes` (Living Notes)
```sql
id uuid primary key,
osis text not null,                             -- canonical anchor
stance text check (stance in ('apologetic','critical','neutral')),
note_md text,
claim_type text check (claim_type in ('textual','historical','doctrinal','logical')),
confidence real,                                -- 0..1
created_at timestamptz default now()
```

### 6.2 `evidence`
```sql
id uuid primary key,
note_id uuid references notes(id) on delete cascade,
source_type text check (source_type in ('openalex','crossref','url','book','dataset','scripture','video')),
source_ref text,                                -- DOI, OpenAlex ID, URL, OSIS, video_id#t=12:34, etc.
quote text,
meta jsonb                                      -- {title, authors, year, etc.}
```

### 6.3 `contra_index`
```sql
id uuid primary key,
osis_a text,
osis_b text,
source text,                                    -- e.g., dataset name
summary text,
meta jsonb
```

### 6.4 `places`
```sql
place text primary key,
confidence real,
lat double precision,
lng double precision,
sources jsonb
```

#### creators
- id (uuid, pk)
- name (text, not null)
- channel (text, optional)
- bio (text, optional)
- tags (text[], optional)
- created_at (timestamptz)

#### videos
- id (uuid, pk)
- creator_id (uuid → creators.id)
- video_id (text, unique)          -- platform id
- title (text)
- url (text)
- published_at (timestamptz)
- duration_seconds (int)
- license (text)
- meta (jsonb)

#### transcript_segments
- id (uuid, pk)
- video_id (uuid → videos.id on delete cascade)
- t_start (real), t_end (real)
- text (text)
- topics (text[])
- entities (jsonb)
- osis_refs (text[])               -- e.g., ['Luke.2.1','Matt.28.19']

#### creator_claims
- id (uuid, pk)
- creator_id (uuid → creators.id)
- video_id (uuid → videos.id)
- segment_id (uuid → transcript_segments.id)
- topic (text)
- stance ('for'|'against'|'nuanced'|'unknown')
- claim_md (text)
- confidence (real)
- created_at (timestamptz)

#### transcript_quotes
- id (uuid, pk)
- video_id (uuid → videos.id)
- segment_id (uuid → transcript_segments.id)
- quote_md (text <= 280 chars)
- osis_refs (text[])
- source_ref (text)                 -- youtube:ID#t=MM:SS
- salience (real)

Note: reuse the existing evidence table by allowing source_type='video' and storing source_ref pointing to transcript_quotes.

---

## 7) Minimal API surface

```
GET  /research/scripture?osis=Luke.2.1-Luke.2.7&translation=SBLGNT
GET  /research/crossrefs?osis=Luke.2.1
GET  /research/contradictions?osis=Luke.2.1-7
GET  /research/geo/search?query=Bethlehem
GET  /research/notes?osis=Luke.2.1
POST /research/notes      -- { osis, stance, claim_type, body, evidence[] }
GET  /features/discovery
GET  /search/openalex?q=Quirinius%20census
GET  /search/crossref?q=Quirinius%20census
POST /ai/agent/deep-dive  -- { osis, options }
```

### Transcripts & Creator Profiles

POST /api/transcripts/ingest
Body: {
  "creator": "Wes Huff",
  "video_id": "YOUTUBE_ID",
  "title": "Video Title",
  "url": "https://youtu.be/...",
  "published_at": "2024-05-12T00:00:00Z",
  "duration_seconds": 3720,
  "license": "user-provided/owned",
  "transcript_format": "vtt|srt|json|text",
  "transcript_payload": "<raw transcript or caption file contents>"
}
Result: { "ok": true, "video_uuid": "..." }

GET /api/creators/search?name=wes%20huff
Result: [{ "id":"...", "name":"Wes Huff" }]

GET /api/creators/:id/topics?topic=baptism&limit=10
Result: {
  "creator":"Wes Huff",
  "topic":"baptism",
  "stance":"for|against|nuanced|unknown",
  "confidence": 0.78,
  "quotes":[
    {"text":"...", "source_ref":"youtube:YOUTUBE_ID#t=12:34", "osis":["John.3.16"]}
  ]
}

GET /api/transcripts/search?osis=Luke.2.1-Luke.2.7
Result: [{ "video_id":"...", "segment_id":"...", "t_start":123.4, "text":"...", "source_ref":"youtube:ID#t=02:03" }]

---

## 8) NEW: YouTube & Creator Transcript Ingestion ("What does Wes think about X?")

### 8.1 Goals
- Ingest YouTube (or any) transcripts that **you provide** into Theoria's resource DB.
- Build **Creator Knowledge Profiles** (e.g., "Wes Huff") that summarize stances by topic and attach time-coded quotes with citations.
- Link transcript content to **OSIS verses** (when verses are mentioned) and to **Claim/Evidence** nodes so it strengthens over time.
- Enable natural queries: "What does Wes think about baptism?" → concise stance summary + quotes + timestamps + video links; optionally compare with other creators.

### 8.2 Ingestion pipeline
1. **Acquire transcript**
   - Accept user-uploaded `.vtt`, `.srt`, `.json`, or raw text (plus the video URL and metadata you enter).
   - Store the raw transcript and segment/timecodes; normalize to UTF-8.
2. **Metadata & provenance**
   - Required: `creator`, `channel`, `video_id`, `title`, `published_at`, `url`, `license`/terms flag (user-supplied), `duration`.
   - Keep a `source_ref` like `youtube:VIDEO_ID#t=MM:SS` for quotes.
3. **Segmentation**
   - Merge short captions into ~10-30-second segments; keep original timecodes.
4. **Enrichment & linking**
   - **Reference detection**: run a Bible reference parser on segment text to detect `John 3:16`, etc.; add OSIS links.
   - **Entity & topic tags**: extract people/places/doctrine terms (e.g., "baptism", "Trinity", "census of Quirinius").
   - **Claim extraction (optional)**: detect declarative claims; store as structured `claims` linked to segments.
   - **Stance extraction (optional)**: per topic, try to infer stance (`for`, `against`, `nuanced`) and confidence; keep rationale text for transparency.
5. **Indexing for retrieval**
   - Create dense vector embeddings for segments + optional BM25 index. Store vector, segment id, and metadata for fast hybrid search.
6. **Quotes & highlights**
   - Auto-summarize each video; mine "top quotes" (short spans with high relevance or rhetorical markers). Store quotes with timestamps, OSIS links (if any), and topics.
7. **Creator profile aggregation**
   - Nightly job rolls up per-creator stance summaries per topic across videos. Track versioning and recency, and show "last updated".

### 8.3 DB schema (additions)

#### `creators`
```sql
id uuid primary key,
name text not null,             -- e.g., "Wes Huff"
channel text,                   -- optional
bio text,
tags text[],
created_at timestamptz default now()
```

#### `videos`
```sql
id uuid primary key,
creator_id uuid references creators(id),
video_id text unique,           -- e.g., YouTube ID
title text,
url text,
published_at timestamptz,
duration_seconds integer,
license text,                   -- user-declared license/terms status
meta jsonb
```

#### `transcript_segments`
```sql
id uuid primary key,
video_id uuid references videos(id) on delete cascade,
t_start real,                   -- seconds
t_end real,
text text,
topics text[],                  -- e.g., ['baptism','Trinity']
entities jsonb,                 -- people/places
osis_refs text[]                -- e.g., ['Luke.2.1','Matt.28.19']
```

#### `creator_claims`
```sql
id uuid primary key,
creator_id uuid references creators(id) on delete cascade,
video_id uuid references videos(id) on delete cascade,
segment_id uuid references transcript_segments(id),
topic text,                     -- normalized topic key
stance text check (stance in ('for','against','nuanced','unknown')),
claim_md text,                  -- short paraphrase + justification
confidence real,                -- 0..1
created_at timestamptz default now()
```

#### `transcript_quotes`
```sql
id uuid primary key,
video_id uuid references videos(id),
segment_id uuid references transcript_segments(id),
quote_md text,                  -- short quote (<= 280 chars) with context
osis_refs text[],
source_ref text,                -- youtube:VIDEO#t=MM:SS
salience real                   -- for ranking in UI
```

> Reuse existing `evidence` table by adding `source_type='video'` and referencing `transcript_quotes` or `videos` via `source_ref`.

### 8.4 Tools (new)

#### `youtube_transcript_ingest`
```json
{
  "name":"youtube_transcript_ingest",
  "description":"Save a transcript (text/VTT/SRT/JSON) and metadata; auto-segment, enrich, and index.",
  "parameters":{"type":"object","properties":{
    "creator":{"type":"string"},
    "video_url":{"type":"string"},
    "video_id":{"type":"string"},
    "title":{"type":"string"},
    "published_at":{"type":"string"},
    "duration_seconds":{"type":"integer"},
    "license":{"type":"string"},
    "transcript_format":{"type":"string","enum":["vtt","srt","json","text"]},
    "transcript_payload":{"type":"string"}
  }, "required":["creator","video_id","title","transcript_format","transcript_payload"]}
}
```

#### `creator_profile_query`
```json
{
  "name":"creator_profile_query",
  "description":"Query a creator's stance and quotes about a topic, with timestamps and links.",
  "parameters":{"type":"object","properties":{
    "creator":{"type":"string"},
    "topic":{"type":"string"},
    "time_from":{"type":"string"},
    "time_to":{"type":"string"},
    "limit":{"type":"integer","default":10},
    "include_quotes":{"type":"boolean","default":true}
  }, "required":["creator","topic"]}
}
```

### 8.5 Query flows (examples)

- **"What does Wes Huff think about baptism?"**
  1) Normalize topic = `baptism`.
  2) Retrieve `creator_claims` for Wes on `baptism` (sorted by recency/confidence).
  3) If sparse/old, run hybrid search over `transcript_segments` with topic filters; propose new claims.
  4) Return: stance summary (`for/against/nuanced` with rationale), top 3 quotes with timestamps & links, and any OSIS-linked verses he cited.

- **"Show me where Wes talks about Luke 2:1-7."**
  1) Search `transcript_segments.osis_refs` for `Luke.2.1-Luke.2.7`.
  2) Return segments and open them side-by-side with the reader (seek video to `t_start`).

- **"Compare Wes vs [Other Creator] on the Trinity."**
  1) Fetch both creators' `creator_claims` on topic `Trinity`.
  2) Show a two-column comparison with quotes and timestamps; compute agreement score.

### 8.6 UI integration

- **Reader context chips**: when a verse is mentioned in any transcript, show a "Creators" chip with a badge (e.g., "3 mentions"). Click → time-coded quotes list.
- **Search bar**: type "Wes on baptism" → navigates to a creator topic page with stance summary, quotes, and video list.
- **Creator profile pages**: overview, topics cloud, stance summaries, recent videos; "evidence" section shows strongest quotes with citations.
- **Quote cards**: copy-able citation string with timestamp link; add to a Living Note as evidence.

### 8.7 Legal, ethical, and quality notes

- **Provenance**: only ingest transcripts you own or have rights to use; or that you, the user, explicitly provide to Theoria.
- **Licensing**: Store user-declared license/terms with each video; respect takedown/opt-out.
- **Quoting**: Keep quotes short; provide timestamped links; prefer paraphrase + cite (fair-use friendly).
- **Attribution**: Always show creator name, video title, and URL with quotes.
- **Drift & changes**: If a creator deletes or edits a video, mark entries as deprecated but keep audit trail.
- **Quality**: Keep stance detection as *assistive*; always provide quotes for verification.

### 8.8 Storage & cost tips

- **Transcript size**: ~150-170 words/minute → ~9-10k words/hour (~7-8k tokens/hour). 
- **Embeddings**: Index at the segment level (~15-30s windows). A 1-hour video becomes ~120-240 segments to embed.
- **Caching**: Cache per-creator/per-topic stance summaries; refresh nightly or on ingestion.
- **Budgeting**: For retrieval, use a small embedding model and hybrid search; reserve larger models for final synthesis when needed.

---

## 9) Modes (preset prompts)

- **Skeptical**: "List contradictions first; prioritize secular scholarship; demand external corroboration; run fallacy audit on arguments."  
- **Apologetic**: "Prefer harmonizations; include conservative scholarship; surface counter-arguments to contradictions."  
- **Neutral scholar**: balanced evidence; report uncertainty/confidence.

Modes change prompts & panel defaults, not datasets.

---

## 10) Roadmap (phased)

**Phase 1** - Reader + Dock basics  
- OSIS-keyed viewer (open translations), Cross-Refs, Morph panel, Notes CRUD, Command palette.

**Phase 2** - Contradictions & Evidence  
- Contradiction panel (seed dataset), Geocoding chip, Deep-Dive report export.

**Phase 3** - Textual & Historical depth  
- Variants/Apparatus panels, scholarly discovery cards, DSS links.

**Phase 4** - Transcripts & Creator Profiles  
- Transcript ingestion, creator profiles, stance/quote mining, "Creators" chip in reader, creator comparison view.

**Phase 5** - Fallacy detection & collaboration
- FallacyDetect model; mode presets; exportable "debate packets"; shared annotation & rating.

---

## Argument Dossier Workspace

A workspace to assemble a debate packet on a claim or doctrine:
- Two columns (Apologetic vs Critical), each with claims, strongest evidence, time-coded quotes, and OSIS citations.
- Drag in verses, creator quotes, and papers; the agent suggests structure and summaries.
- Export to Markdown/HTML/PDF with a manifest of sources and licenses.

**Acceptance**
- Create a dossier for "Census of Quirinius": contains Luke 2 / Matthew 2 passages, 2-3 scholarly refs, and 3 creator quotes; exports with citations.

---

## 11) Acceptance criteria

- Typographic artifacts removed across the file; UTF-8 clean.
- New "Creator & Media Profiles" pillar appears under Product pillars.
- API lists transcript ingestion and creator/topic retrieval endpoints.
- Data model tables for creators, videos, segments, creator_claims, transcript_quotes are documented.
- Reader shows a "Creators" chip on verses that appear in transcripts; clicking shows quotes + timestamps.
- Query "What does <Creator> think about <Topic>?" returns stance + 3 quotes with timestamps and OSIS refs.
- Deep-Dive reports include transcript evidence automatically.
- Research Trails section present; can view and replay an agent trail.
- Argument Dossier section present; sample dossier criteria met.

---

*End of spec.*
