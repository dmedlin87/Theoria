# TheoEngine — Deep Research & Implementation Plan
_Date: 2025-09-27_

> Comprehensive synthesis of our conversation, your **TheoEngine Feature Research & Strategy** PDF, and supplemental research; includes verified context, gaps, and a practical roadmap with implementation cut‑lines.

---

## 1) Executive Summary

**TheoEngine’s position.** TheoEngine sits between content‑heavy incumbents (Logos/Accordance) and AI‑native research assistants (e.g., Scite), combining a grounded, OSIS‑aware RAG copilot with hybrid search. The strategic thrust is to deepen that synthesis into a **discover‑and‑synthesize** workspace with trust, provenance, and extensibility as core pillars. fileciteturn1file0L21-L28 fileciteturn1file3L11-L21

**Four strategic levers (from the PDF).** (1) **Knowledge‑graph expansion**, (2) **Paradigm‑shift UX** from search to discovery, (3) **Theological AI integrity** (doctrinal guardrails + full verifiability), (4) **Open ecosystem** (APIs + plugins). fileciteturn1file3L7-L21

**What this plan delivers.** A concrete feature roadmap (quick wins → moat builders), repo‑aligned implementation suggestions, doctrinal and auditability guardrails, and ops guidance to keep costs predictable while scaling.

---

## 2) What You Already Have (from the PDF & prior context)

- **Connectors & ingestion** for local files, URLs, and multimedia; OSIS normalization and hybrid search tailored for scholarly inquiry. fileciteturn1file0L21-L25 fileciteturn1file3L71-L75  
- **RAG copilot** with verifiable citations and conversation guardrails; CLI‑driven ingestion & enrichment jobs; sermon/Q&A exports; trend monitoring. fileciteturn1file0L40-L46 fileciteturn1file4L117-L121 fileciteturn1file4L23-L31

> **Verification note:** We did not have direct GitHub access via web search at the time of writing; this inventory is grounded in your uploaded PDF and prior feature descriptions. See §10 for assumptions and follow‑ups.

---

## 3) Competitive Landscape (PDF synthesis)

The comparison table in your PDF frames TheoEngine against Logos, Accordance, Scite, Zotero, and Glean across source acquisition, retrieval UX, guardrails, workflows, stewardship, analytics, ecosystem, and ops. It highlights TheoEngine’s strengths in OSIS‑aware retrieval and RAG, and gaps in historical text pipelines, TEI/graph depth, CSL exports, and ecosystem integrations. fileciteturn1file3L31-L40 fileciteturn1file4L167-L176

---

## 4) Gaps & Opportunities (synthesized)

1) **Deep standards alignment**: keep OSIS for canonical refs; add **TEI P5** to encode speakers, citations, apparatus, and linguistic features—enabling fine‑grained IR & graph views. citeturn0search0turn0search10turn0search15  
2) **Historical text pipeline**: add OCR/HTR for scans and early print; consider AI models like **Transkribus** to handle non‑Latin scripts and degraded print. citeturn0search4turn0search19  
3) **Image provenance & deep zoom**: integrate **IIIF** manifests + a viewer (e.g., Mirador/Universal Viewer) so citations can jump to a page/region. citeturn0search2turn0search7turn0search12turn0search17  
4) **Hybrid ranking uplift**: replace manual weighting with **Reciprocal Rank Fusion (RRF)** for more stable vector+lexical merges. citeturn0search8turn0search18  
5) **Doctrinal lenses**: add user‑selectable hermeneutical profiles (Neutral/Apologetic/Skeptical) with disclosure; retrieval/prompting adapts per lens. fileciteturn1file2L16-L19  
6) **Discovery UX**: timelines, verse‑surge trends, speaker/author faceting, and map/story navigators as first‑class views. fileciteturn1file3L11-L13  
7) **CSL bibliographies & ref‑mgr hooks**: export CSL‑JSON; optional Zotero/Mendeley integration. fileciteturn1file4L37-L42  
8) **Ops & cost controls**: ingestion SLOs, idempotence on sha256, Celery retries/DLQs, metrics, budget alerts.

---

## 5) Proposed Roadmap

### 0–3 Months (Quick Wins)
- **RRF fusion** behind a feature flag; ship an eval harness + dashboard. citeturn0search8  
- **Verifiable snippet UX+**: inline quoted span, “Open page/line,” OSIS chip everywhere; persist retrieval sets in an **audit trail**.
- **CSL export v1**: per‑item and batch CSL‑JSON; BibTeX/RIS as stretch. fileciteturn1file4L37-L42  
- **Study Mode**: simplified UI with always‑visible citations + glossary tooltips.
- **Analytics v1**: coverage of cited snippets, abstention rate, hybrid vs lexical CTR.

### 3–9 Months (Strategic)
- **TEI pilot** on a focused corpus (patristics or DSS subset); index TEI facets (speaker, lemma, apparatus). citeturn0search0turn0search15  
- **OCR/HTR lane**: auto‑detect image‑only PDFs → HTR (Transkribus) → post‑OCR correction → chunk. citeturn0search4  
- **IIIF in the UI**: render manifests; link citations to image regions. citeturn0search2  
- **Doctrinal lenses v1**: mode toggle; retrieval boosts; prompt templates; disclosure chip.
- **Public API (read‑only)**: search/verse/citation endpoints with tenant keys.

### 9–18 Months (Moat Builders)
- **TEI‑backed knowledge graph** (Entities, VerseEntityLink); canon‑aware timelines/maps.
- **Cross‑lingual concordances**: parallel panes aligned at verse/morph layer.
- **Plugin marketplace**: Evidence Cards, Lectionary Planner, Reading Plans.
- **Multi‑tenant hardening + cost governance** (quotas, budget alerts, autoscaling).

---

## 6) Implementation Plan — By Component

### Backend (FastAPI + Postgres/pgvector + Celery)
- **Hybrid search**: expose two ranked lists (BM25, embeddings) and **fuse via RRF**; keep current weighting as fallback; add per‑query knobs (k, cutoffs). citeturn0search8  
- **Ingestion**: early **sha256** de‑dup; task graph (parse → enrich → embed → index); retries & DLQ; resumable ingest markers.
- **TEI support**: TEI→normalized JSON pipeline; new tables for **Entity** and **VerseEntityLink**; index TEI facets for faceting/search. citeturn0search0  
- **OCR/HTR**: OCR fallback when `text_len==0`; enqueue HTR; track provenance of each stage. citeturn0search4  
- **IIIF**: store manifest URLs and region selectors; return deep links alongside OSIS citations. citeturn0search2  
- **CSL export**: route `/export/csl` returning CSL‑JSON for selected hits/passages; add RIS/BibTeX later.
- **Guardrails & audit**: abstain‑when‑uncertain policy; every answer carries citations; persist trail (retrieval set, prompts, model, post‑checks).

### Frontend (Next.js)
- **Search**: filters for collection/author/source; add time slider; chip‑style OSIS; inline quote+“open in context” actions.
- **Verse view**: side panels for apparatus/speaker; **timeline sparkline**; “views” menu (parallel, concordance, variants).
- **Timelines & Maps**: dedicated routes (`/timeline/[osis]`, `/map`); drill‑downs to sources.
- **IIIF viewer**: Mirador/UniversalViewer component; link from citations to page regions.
- **Mode toggle**: Neutral/Apologetic/Skeptical with disclosure; tooltips explain the lens.
- **Study Mode**: larger typography, persistent citations, term popovers.

### Workflows & Ops
- **Eval harness**: query sets with ground‑truth judgments; NDCG/Recall; A/B of fusion methods.
- **Observability**: Prometheus metrics (ingest latency, queue depth, RAG token cost); Sentry for API/UI; OpenTelemetry traces.
- **Budget controls**: per‑tenant quotas; alert on spend; cache hot passages/snippets.

---

## 7) Policies, Standards & Rationale (key references)

- **TEI P5 (Text Encoding Initiative)** — modular XML encoding for scholarly texts; supports deep structures (speakers, apparatus, citations). citeturn0search0turn0search15  
- **OSIS (Open Scripture Information Standard)** — XML schema for Bibles/commentaries with a formal canonical reference system. citeturn0search1turn0search6turn0search11  
- **IIIF** — open standards for delivering high‑quality images/A/V; enables deep‑zoom viewers and interoperable manifests. citeturn0search2turn0search7turn0search12  
- **RRF (Reciprocal Rank Fusion)** — simple, robust method to fuse multiple ranked lists; shown to outperform individual rankers and Condorcet methods. citeturn0search8turn0search18  
- **OCR/HTR (Transkribus)** — AI models for printed and handwritten historical documents; customizable per script/typeface. citeturn0search4turn0search19

---

## 8) Success Metrics & Feedback Loops

- **Retrieval**: NDCG@10, Recall@k, Hybrid‑vs‑Lexical CTR.  
- **Generation**: % answers with **direct snippet citations**, abstention rate, post‑edit delta.  
- **Cost/Perf**: tokens/answer, p95 latency, GPU hours.  
- **Trust**: user feedback on accuracy/neutrality; red‑team sets around hot topics; doctrine‑lens satisfaction.

---

## 9) Risks & Mitigations

- **Licensing**: modern translations/commentaries may be paywalled → focus on public‑domain + partnerships; show licenses in UI.  
- **Bias & misattribution**: doctrinal lenses clearly disclosed; show contrasting views; abstain when ungrounded. fileciteturn1file2L16-L19  
- **Ops drift/cost**: autoscaling, caching, quotas, and explicit budget alarms before scale‑out.

---

## 10) Verification Notes & Follow‑ups

- **Repo access**: The GitHub repository wasn’t publicly accessible via web search at the time of writing; verification relied on your **uploaded PDF** and prior context. For a code‑level gap analysis (e.g., confirm RRF exists or not, audit trail schema names), grant read access or share a tarball, and I’ll produce line‑level diffs and GitHub‑ready issues.

**Primary PDF references:** executive positioning & levers, landscape matrix, and deep‑dive sections on source acquisition, discovery UX, doctrinal guardrails, ecosystem, and ops. fileciteturn1file0L21-L28 fileciteturn1file3L7-L21 fileciteturn1file3L31-L40 fileciteturn1file1L96-L105

---

## 11) Immediate Ticket Starters (copy‑paste)

- **Search**: Implement RRF fusion (feature flag); add eval harness; emit metrics.  
- **UI**: Add inline quote + “Open page/line”; OSIS chips on all cards; Study Mode toggle.  
- **Export**: `/export/csl` (CSL‑JSON); binder for BibTeX/RIS.  
- **Standards**: TEI pilot importer + TEI facet indexing; provenance (PROV‑O‑like) chain in DB.  
- **Pipelines**: OCR fallback task with retries & DLQ; sha256 idempotence on ingest.  
- **Ecosystem**: read‑only public API (search/verse/citation) with tenant keys & rate limits.

---

### Appendix: Quick Links
- TEI P5 Guidelines (overview/PDF/infra). citeturn0search0turn0search5turn0search15  
- OSIS standard (CrossWire overview + background). citeturn0search1turn0search11  
- IIIF (overview, how it works, benefits, viewers). citeturn0search2turn0search7turn0search12turn0search17  
- Reciprocal Rank Fusion (SIGIR’09). citeturn0search8turn0search18  
- Transkribus (OCR/HTR). citeturn0search4turn0search19
