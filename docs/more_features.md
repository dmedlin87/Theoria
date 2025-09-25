# TheoEngine: Deepâ€‘Research Bible Reader & Critical Analysis Agent

**Goal.** A verseâ€‘first Bible reader that turns every passage into a research workspace: textual variants, crossâ€‘references, morphology, historical context, contradiction/harmony checks, apologetic vs. skeptical notes, and citable evidenceâ€”on tap while you read.

**Why this approach.** Open biblical corpora (OSIS references, open translations and morphology datasets), crossâ€‘reference and geocoding datasets, and open scholarly indexes (e.g., OpenAlex/Crossref) now make a serious research UX feasible. The agent stays retrievalâ€‘grounded, runs short planning steps, calls tools for deterministic data, and only then writes analysis with citations.

---

## 1) Product pillars

1. **Reader + Research Dock** (verseâ€‘anchored)
   - Chips per verse/selection open panels: **Crossâ€‘References**, **Textual Variants**, **Morph & Interlinear**, **Historical Context**, **Contradictions & Harmonies**, **Commentaries & Perspectives**, and **Living Study Notes**.
   - Split view: pin any two passages with synchronized scrolling and highlight parallels.
   - Command palette: â€œCompare translationsâ€, â€œOpen contradictionsâ€, â€œSearch papersâ€, â€œShow DSS linksâ€, etc.

2. **Agentic analysis (plan â†’ tool calls â†’ report)**
   - ReActâ€‘style short plan â†’ retrieval/comparison tools â†’ twoâ€‘column summary (Apologetic vs Skeptical) with footnotes.
   - Always â€œtools first, generation secondâ€ for auditability.

3. **Living Notes (gets smarter as you study)**
   - Structured **Claim Cards** (type/stance/confidence) + **Evidence Cards** (citations). Reuse raises a sourceâ€™s credibility weight across the app.

4. **Licensingâ€‘aware content**
   - Prefer open corpora first (e.g., SBLGNT licensing, MorphGNT, OSHB). Clearly badge licenses in the UI and respect redistribution limits for modern study notes (e.g., NET notes).

---

## 2) Core datasets & libraries (starter set)

- **OSIS** (canonical verse IDs): all notes, claims, and citations are keyed to OSIS (e.g., `Luke.2.1`), making them portable across translations.
- **Bible modules**: SWORD/JSword modules for public translations and dictionaries (OSIS/TEI/ThML).
- **Greek (NT)**: SBLGNT text + MorphGNT morphology (merge serverâ€‘side; observe licenses).
- **Hebrew (OT)**: OSHB (text + morphology) and allied lexica where permissible.
- **Crossâ€‘references**: Open datasets (e.g., TSKâ€‘style / OpenBible crossâ€‘refs). 
- **Geocoding**: Open Bible atlas/places datasets with confidence scores.
- **Scholarly discovery**: OpenAlex and Crossref APIs for papers/books (store IDs, DOIs, titles, venues, years).
- **Dead Sea Scrolls links**: outward links to authoritative collections for relevant verses.
- **Contradiction seeds**: community datasets (e.g., SAB/BibViz) clearly labeled as nonâ€‘peerâ€‘reviewed; balance with apologetic harmonizations.

> All external datasets should be cached with provenance and licensing metadata. Show license badges per panel; block export of restricted content.

---

## 3) UX blueprint (readerâ€‘first, researchâ€‘instant)

**Layout**
- **Top bar**: translation dropdown, search, **Mode** toggle (Neutral / Skeptical / Apologetic), â€œDeepâ€‘Diveâ€ button.
- **Reader** (center): OSISâ€‘anchored text; verse numbers show hover badge with quick actions.
- **Research Dock** (right): chips expand into panels.
- **Split view**: pin two passages (e.g., Luke 2 vs Matt 2), sync scroll.

**Panels**
- **Crossâ€‘References** â€” ranked graph of related verses; open sideâ€‘byâ€‘side.
- **Textual Variants** â€” base text, major variants; translation diffs; apparatus notes where available.
- **Morph & Interlinear** â€” lemma, parsing, glosses.
- **Historical Context** â€” timeline card (who/when/where), brief summaries, links to external sources; show DSS links when relevant.
- **Contradictions & Harmonies** â€” known entries with citations, plus user/vetted notes.
- **Commentaries & Perspectives** â€” tabs for â€œApologeticâ€ vs â€œCriticalâ€ (e.g., Bart D. Ehrman) with sideâ€‘byâ€‘side arguments.
- **Study Notes (Living)** â€” your structured notes: claims, fallacies flagged, verdicts, sources; all OSISâ€‘anchored.

**Ergonomics**
- Hover actions on verse numbers; inline highlights where crossâ€‘refs or variants exist.
- Command palette: oneâ€‘keystroke to open panels/actions.
- Oneâ€‘click **Deepâ€‘Dive**: runs the agent workflow and opens a printable, citable report.

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

### A) Passage Deepâ€‘Dive
**Prompt**: â€œDeepâ€‘dive Luke 2:1â€“7; show contradictions vs harmonies; add history on Quirinius/Herod.â€  
**Plan**: `scripture_retrieve` â†’ `crossrefs_lookup` â†’ `variants_apparatus` â†’ `historicity_search` â†’ `contradiction_index` â†’ `report_build` (Apologetic vs Critical, footnoted).

### B) Fallacy Audit (argument paragraph)
Segment claims â†’ `fallacy_detect` â†’ check premises via `scripture_retrieve`/`variants_apparatus` â†’ report with labels & receipts.

### C) Geoâ€‘Temporal Sanity Check
Extract names/dates/places â†’ `geo_places` + timeline overlay â†’ flag infeasible legs; annotate assumptions.

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

---

## 7) Minimal API surface

```
GET  /api/passage?osis=Luke.2.1-Luke.2.7&translation=SBLGNT
GET  /api/crossrefs?osis=Luke.2.1
GET  /api/variants?osis=Luke.2.2
GET  /api/geo?place=Bethlehem
GET  /api/notes?osis=Luke.2.1
POST /api/notes        -- { osis, stance, claim_type, note_md, evidence[] }
GET  /api/contradictions?osis=Luke.2
GET  /api/search/openalex?q=Quirinius%20census
GET  /api/search/crossref?q=Quirinius%20census
POST /api/agent/deep-dive  -- { osis, options }
```

---

## 8) NEW: YouTube & Creator Transcript Ingestion (â€œWhat does Wes think about X?â€)

### 8.1 Goals
- Ingest YouTube (or any) transcripts that **you provide** into TheoEngineâ€™s resource DB.
- Build **Creator Knowledge Profiles** (e.g., â€œWes Huffâ€) that summarize stances by topic and attach timeâ€‘coded quotes with citations.
- Link transcript content to **OSIS verses** (when verses are mentioned) and to **Claim/Evidence** nodes so it strengthens over time.
- Enable natural queries: â€œWhat does Wes think about baptism?â€ â†’ concise stance summary + quotes + timestamps + video links; optionally compare with other creators.

### 8.2 Ingestion pipeline
1. **Acquire transcript**
   - Accept userâ€‘uploaded `.vtt`, `.srt`, `.json`, or raw text (plus the video URL and metadata you enter).
   - Store the raw transcript and segment/timecodes; normalize to UTFâ€‘8.
2. **Metadata & provenance**
   - Required: `creator`, `channel`, `video_id`, `title`, `published_at`, `url`, `license`/terms flag (userâ€‘supplied), `duration`.
   - Keep a `source_ref` like `youtube:VIDEO_ID#t=MM:SS` for quotes.
3. **Segmentation**
   - Merge short captions into ~10â€“30â€‘second segments; keep original timecodes.
4. **Enrichment & linking**
   - **Reference detection**: run a Bible reference parser on segment text to detect `John 3:16`, etc.; add OSIS links.
   - **Entity & topic tags**: extract people/places/doctrine terms (e.g., â€œbaptismâ€, â€œTrinityâ€, â€œcensus of Quiriniusâ€).
   - **Claim extraction (optional)**: detect declarative claims; store as structured `claims` linked to segments.
   - **Stance extraction (optional)**: per topic, try to infer stance (`for`, `against`, `nuanced`) and confidence; keep rationale text for transparency.
5. **Indexing for retrieval**
   - Create dense vector embeddings for segments + optional BM25 index. Store vector, segment id, and metadata for fast hybrid search.
6. **Quotes & highlights**
   - Autoâ€‘summarize each video; mine â€œtop quotesâ€ (short spans with high relevance or rhetorical markers). Store quotes with timestamps, OSIS links (if any), and topics.
7. **Creator profile aggregation**
   - Nightly job rolls up perâ€‘creator stance summaries per topic across videos. Track versioning and recency, and show â€œlast updatedâ€.

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
  "description":"Query a creatorâ€™s stance and quotes about a topic, with timestamps and links.",
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

- **â€œWhat does Wes Huff think about baptism?â€**
  1) Normalize topic = `baptism`.
  2) Retrieve `creator_claims` for Wes on `baptism` (sorted by recency/confidence).
  3) If sparse/old, run hybrid search over `transcript_segments` with topic filters; propose new claims.
  4) Return: stance summary (`for/against/nuanced` with rationale), top 3 quotes with timestamps & links, and any OSISâ€‘linked verses he cited.

- **â€œShow me where Wes talks about Luke 2:1â€“7.â€**
  1) Search `transcript_segments.osis_refs` for `Luke.2.1â€‘Luke.2.7`.
  2) Return segments and open them sideâ€‘byâ€‘side with the reader (seek video to `t_start`).

- **â€œCompare Wes vs [Other Creator] on the Trinity.â€**
  1) Fetch both creatorsâ€™ `creator_claims` on topic `Trinity`.
  2) Show a twoâ€‘column comparison with quotes and timestamps; compute agreement score.

### 8.6 UI integration

- **Reader context chips**: when a verse is mentioned in any transcript, show a â€œCreatorsâ€ chip with a badge (e.g., â€œ3 mentionsâ€). Click â†’ timeâ€‘coded quotes list.
- **Search bar**: type â€œWes on baptismâ€ â†’ navigates to a creator topic page with stance summary, quotes, and video list.
- **Creator profile pages**: overview, topics cloud, stance summaries, recent videos; â€œevidenceâ€ section shows strongest quotes with citations.
- **Quote cards**: copyâ€‘able citation string with timestamp link; add to a Living Note as evidence.

### 8.7 Legal, ethical, and quality notes

- **Provenance**: only ingest transcripts you own or have rights to use; or that you, the user, explicitly provide to TheoEngine.
- **Licensing**: Store userâ€‘declared license/terms with each video; respect takedown/optâ€‘out.
- **Quoting**: Keep quotes short; provide timestamped links; prefer paraphrase + cite (fairâ€‘use friendly).
- **Attribution**: Always show creator name, video title, and URL with quotes.
- **Drift & changes**: If a creator deletes or edits a video, mark entries as deprecated but keep audit trail.
- **Quality**: Keep stance detection as *assistive*; always provide quotes for verification.

### 8.8 Storage & cost tips

- **Transcript size**: ~150â€“170 words/minute â†’ ~9â€“10k words/hour (~7â€“8k tokens/hour). 
- **Embeddings**: Index at the segment level (~15â€“30s windows). A 1â€‘hour video becomes ~120â€“240 segments to embed.
- **Caching**: Cache perâ€‘creator/perâ€‘topic stance summaries; refresh nightly or on ingestion.
- **Budgeting**: For retrieval, use a small embedding model and hybrid search; reserve larger models for final synthesis when needed.

---

## 9) Modes (preset prompts)

- **Skeptical**: â€œList contradictions first; prioritize secular scholarship; demand external corroboration; run fallacy audit on arguments.â€  
- **Apologetic**: â€œPrefer harmonizations; include conservative scholarship; surface counterâ€‘arguments to contradictions.â€  
- **Neutral scholar**: balanced evidence; report uncertainty/confidence.

Modes change prompts & panel defaults, not datasets.

---

## 10) Roadmap (phased)

**Phase 1** â€” Reader + Dock basics  
- OSISâ€‘keyed viewer (open translations), Crossâ€‘Refs, Morph panel, Notes CRUD, Command palette.

**Phase 2** â€” Contradictions & Evidence  
- Contradiction panel (seed dataset), Geocoding chip, Deepâ€‘Dive report export.

**Phase 3** â€” Textual & Historical depth  
- Variants/Apparatus panels, scholarly discovery cards, DSS links.

**Phase 4** â€” Transcripts & Creator Profiles  
- Transcript ingestion, creator profiles, stance/quote mining, â€œCreatorsâ€ chip in reader, creator comparison view.

**Phase 5** â€” Fallacy detection & collaboration  
- FallacyDetect model; mode presets; exportable â€œdebate packetsâ€; shared annotation & rating.

---

## 11) Acceptance criteria (MVP for transcripts)

- Upload a Wes Huff transcript (VTT).  
- App segments, indexes, detects `John 3:16` mentions, and extracts 3 top quotes.  
- Query: â€œWhat does Wes think about baptism?â€ returns a stance summary + 3 quotes with timestamps and links.  
- From `John 3:16` in the reader, the â€œCreatorsâ€ chip shows Wesâ€™s mentions and opens the quotes pane.  
- Add one quote as evidence to a Living Note; export a Deepâ€‘Dive report with that evidence attached.

---

*End of spec.*