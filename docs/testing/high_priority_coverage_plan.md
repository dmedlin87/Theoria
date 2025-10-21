# High-Priority Test Coverage Expansion Plan

## Overview
The latest coverage review highlights that our backend coverage is only **28.3%** overall, with multiple critical modules below 20% coverage, far from the 80–90% targets set in the testing ADR.【F:docs/archive/planning/COVERAGE_SUMMARY.md†L1-L132】 Among the highest-impact gaps are three packages in the API service layer:

| Rank | Module | Current Coverage | Target |
|------|--------|------------------|--------|
| 1 | `theo/services/api/app/core` | 0.0% | ≥90% |
| 2 | `theo/services/api/app/ingest` | 16.2% | ≥90% |
| 3 | `theo/services/api/app/retriever` | 12.8% | ≥90% |

This document inventories the tests we need to build to bring each module close to 90% line coverage while protecting their most failure-prone behaviours.

---

## 1. `theo/services/api/app/core`
The `core` package contains legacy shim modules that re-export functionality from the application facades with deprecation warnings. Even though the logic surface is small, missing coverage risks regressions in import-time warnings and symbol forwarding.

### Key Surfaces to Exercise
* Deprecation warnings emitted on import for each shim (`database`, `runtime`, `secret_migration`, `settings`, `settings_store`, `version`).【F:theo/services/api/app/core/database.py†L1-L25】【F:theo/services/api/app/core/runtime.py†L1-L15】【F:theo/services/api/app/core/secret_migration.py†L1-L15】【F:theo/services/api/app/core/settings.py†L1-L23】【F:theo/services/api/app/core/settings_store.py†L1-L27】【F:theo/services/api/app/core/version.py†L1-L15】
* `__all__` exports remain aligned with the facade API to prevent dynamic import breakage.
* Forwarded call semantics—each shim should invoke the underlying facade function without mutating arguments.

### Planned Tests
| Type | Scenario | Notes |
|------|----------|-------|
| Unit | `pytest.warns(DeprecationWarning)` around importing each shim module. | Use `importlib.reload` to verify warnings fire once per import.
| Unit | Validate `__all__` contents match expected symbol names, and `getattr` returns the facade object. | Monkeypatch the facade symbols with sentinels before import to ensure forwarding.
| Unit | Verify forwarded functions propagate return values and exceptions unchanged. | Patch facade callables to record arguments; assert passthrough behaviour for `get_settings`, `require_setting`, `migrate_secret_settings`, and `allow_insecure_startup`.
| Regression | When facade raises, ensure shim re-raises the same exception type (e.g., `SettingNotFoundError`). | Helps catch accidental wrapping in future refactors.

### Additional Coverage Boosters
* Use parametrised tests to cover all shim modules in a single file to minimise duplication.
* Add a docstring assertion test to ensure warning text stays actionable (guards accidental edits).

### Progress
* ✅ Added `tests/services/api/app/core/test_shims.py` to assert each shim emits a deprecation warning on first import, preserves its `__all__` exports, and forwards facade calls without mutating arguments.

---

## 2. `theo/services/api/app/ingest`
This package orchestrates ingestion flows (file, transcript, URL, OSIS), metadata parsing, network hygiene, and embedding generation. Failures here directly affect content availability and safety, so we need a mix of unit, integration, and property-style tests.

### High-Risk Components
* **Orchestrator + Pipeline wiring** – `IngestOrchestrator` handles retries, fallbacks, and state mutation across heterogeneous stages.【F:theo/services/api/app/ingest/orchestrator.py†L11-L123】
* **Pipeline entry points** – `PipelineDependencies`, `_ensure_success`, and the `run_pipeline_for_*` helpers shape context, instrumentation, and persistence behaviour.【F:theo/services/api/app/ingest/pipeline.py†L93-L377】
* **Network guards** – Host validation, redirect handling, and fetch limits in `network.py` defend against SSRF and unbounded downloads.【F:theo/services/api/app/ingest/network.py†L1-L334】【F:theo/services/api/app/ingest/network.py†L200-L425】
* **Metadata & chunking** – Markdown frontmatter parsing, guardrail extraction, and chunk assembly drive downstream retrieval quality.【F:theo/services/api/app/ingest/metadata.py†L1-L199】
* **Embedding service** – Lazy loading, caching, resilience hooks, and deterministic fallback are critical for deterministic tests and production parity.【F:theo/services/api/app/ingest/embeddings.py†L12-L177】

### Planned Tests

#### 2.1 Unit Tests
| Focus | Scenario | Techniques |
|-------|----------|------------|
| Orchestrator | Success path aggregates stage outputs and metadata; failure path returns immediately with last error. | Stub stages implementing `SourceFetcher`/`Parser` to supply deterministic state transitions. Assert attempts counting, state accumulation, and failure short-circuit.
| Orchestrator | Retry logic honours `ErrorPolicyDecision` (`retry=True`, `fallback` swap, `max_retries`). | Inject a fake `error_policy` via `IngestContext` returning scripted decisions; assert fallback stage invocation and final failure.
| PipelineDependencies | `build_context` defaults to real facades yet falls back to `NullGraphProjector` when `get_graph_projector` raises.【F:theo/services/api/app/ingest/pipeline.py†L93-L120】 | Monkeypatch facades to raise/succeed and assert instrumentation wiring.
| `_ensure_success` | Returns document on success; raises underlying exception or `UnsupportedSourceError` when failures lack metadata.【F:theo/services/api/app/ingest/pipeline.py†L129-L143】 | Construct `OrchestratorResult` fixtures representing each branch.
| Title factories | `_file_title_default` and `_transcript_title_default` normalise `Path` and string values.【F:theo/services/api/app/ingest/pipeline.py†L220-L232】 | Parametrised tests with `Path`, string, and missing inputs.
| URL pipeline | `_UrlDocumentPersister` delegates to transcript vs. text persisters by `source_type` flag.【F:theo/services/api/app/ingest/pipeline.py†L334-L369】 | Use spy persisters to assert dispatch decisions.
| `ensure_url_allowed` wrapper | Allows explicitly whitelisted hosts even when DNS resolution fails, while still blocking private ranges.【F:theo/services/api/app/ingest/pipeline.py†L145-L189】 | Patch `ingest_network` helpers; simulate allowed/blocked host permutations.
| Network validation | Cover `normalise_host`, `resolve_host_addresses`, allow/deny lists, and blocked CIDRs.【F:theo/services/api/app/ingest/network.py†L29-L153】 | Freeze DNS results with monkeypatches; leverage `pytest.mark.parametrize` for IPv4/IPv6 cases.
| Redirect handler | Guard against redirect loops, excessive depth, and missing `Location`.【F:theo/services/api/app/ingest/network.py†L155-L189】 | Construct fake responses/opener stubs.
| `fetch_web_document` | Enforces byte limits, timeout translation, metadata enrichment, and ensures final URL revalidation.【F:theo/services/api/app/ingest/network.py†L191-L314】 | Feed deterministic `BytesIO` response objects; assert errors when `Content-Length` or stream exceeds `max_bytes`.
| YouTube helpers | `extract_youtube_video_id` handles watch, shorts, embed, and youtu.be shapes; `is_youtube_url` matches canonical hosts.【F:theo/services/api/app/ingest/network.py†L400-L425】 | Table-driven tests for representative URLs and unsupported hosts.
| Metadata parsing | `parse_frontmatter_from_markdown`, `parse_text_file`, `merge_metadata`, and guardrail helpers normalise YAML and nested structures.【F:theo/services/api/app/ingest/metadata.py†L51-L199】 | Include property-style checks ensuring overrides win and duplicates deduplicate.
| Embeddings cache | `EmbeddingService.embed` uses deterministic fallback, caches hits, and records cache stats when `unique_misses` shrink.【F:theo/services/api/app/ingest/embeddings.py†L42-L126】【F:theo/services/api/app/ingest/embeddings.py†L150-L212】 | Patch `_RuntimeFlagModel` to raise; inspect `_cache` ordering and metadata on spans via test tracer.
| Embeddings resilience | When `_encode` triggers `ResilienceError`, ensure exception bubbles and span attributes are set.【F:theo/services/api/app/ingest/embeddings.py†L123-L176】 | Fake backend raising `ResilienceError` with metadata.

#### 2.2 Integration Tests
| Flow | Scenario | Notes |
|------|----------|-------|
| File pipeline | Compose stub `FileSourceFetcher`, `FileParser`, and `TextDocumentPersister` to assert document persistence and instrumentation context from `_orchestrate`. | Use in-memory SQLAlchemy session and sentinel document objects to avoid disk IO.
| Transcript pipeline | Validate `_transcript_title_default`, chunk merging, and `TranscriptDocumentPersister` wiring by simulating transcript state. | Reuse `TranscriptSegment` fixtures to ensure metadata persists.
| URL pipeline | Simulate YouTube ingest end-to-end with patched network + transcript fixtures to cover `_UrlDocumentPersister`, metadata merging, and `_ensure_success`. | Use `ensure_url_allowed` allowlist path plus transcript fixtures from `fixtures/youtube`.
| OSIS import | Provide small OSIS XML fixture to confirm commentary seeds stored and error path when parser omits `commentary_result`. | Mock `OsisCommentaryParser` to drop payload for negative case.【F:theo/services/api/app/ingest/pipeline.py†L234-L268】

#### 2.3 Property / Fuzz Tests
* Property-based test around `merge_metadata` ensuring associative merging regardless of dict order (Hypothesis).【F:theo/services/api/app/ingest/metadata.py†L122-L134】
* Generate random guardrail inputs (lists/strings) to guarantee `_normalise_guardrail_collection` deduplicates and strips whitespace. 【F:theo/services/api/app/ingest/metadata.py†L167-L197】
* Hypothesis strategies for URLs to stress `normalise_host` and blocked network parsing without hitting the network stack.【F:theo/services/api/app/ingest/network.py†L29-L107】

#### 2.4 Fixtures & Utilities
* Shared fake settings object exposing ingest allow/block lists and user agent.
* Stub `ErrorPolicyDecision` dataclass to reuse across orchestrator tests.
* Reusable `FakeResponse` class for network tests (supports `.read`, `.headers`, `.geturl`).

### Progress
* ✅ Covered `ensure_url_allowed` allow-list bypass and blocked-network rejection paths through `tests/services/api/app/ingest/test_pipeline_url_guards.py`.
* ✅ Added `tests/services/api/app/ingest/test_metadata.py` to verify `merge_metadata` nested override semantics.
* ✅ Implemented `tests/services/api/app/ingest/test_pipeline_core.py` to exercise `PipelineDependencies`, `_ensure_success`, default title factories, and `_UrlDocumentPersister` dispatch logic.
* ✅ Added `tests/services/api/app/ingest/test_orchestrator.py` to cover success, retry/fallback, and terminal failure behaviours of `IngestOrchestrator`.
* ✅ Added `tests/services/api/app/ingest/test_network.py` to cover host normalisation, redirect loop detection, fetch byte limits, and YouTube helper utilities.
* ✅ Expanded `tests/services/api/app/ingest/test_metadata.py` with guardrail property tests, metadata serialisation, topic aggregation, and HTML parsing checks.
* ✅ Added `tests/services/api/app/ingest/test_embeddings.py` to validate embedding cache behaviour, resilience telemetry, and lexical representation fallbacks.

---

## 3. `theo/services/api/app/retriever`
The retriever package powers hybrid semantic + lexical search, annotation hydration, and document APIs. Coverage must span ranking math, guardrail filters, and database interactions.

### High-Risk Components
* **Hybrid ranking pipeline** – Tokenisation, highlight extraction, candidate scoring, guardrail filters, and fallbacks in `hybrid.py`.【F:theo/services/api/app/retriever/hybrid.py†L1-L600】
* **Document API helpers** – Pagination, detail expansion, and annotation CRUD in `documents.py`.【F:theo/services/api/app/retriever/documents.py†L1-L200】
* **Annotation utilities** – JSON normalisation, legacy support, and indexing logic.【F:theo/services/api/app/retriever/annotations.py†L1-L150】
* **Metadata composition** – `compose_passage_meta` merges document context for clients.【F:theo/services/api/app/retriever/utils.py†L1-L49】

### Planned Tests

#### 3.1 Unit Tests
| Focus | Scenario | Techniques |
|-------|----------|------------|
| Tokenisation | `_tokenise`, `_lexical_score`, `_snippet`, `_build_highlights` handle mixed case, duplicate tokens, and length limits.【F:theo/services/api/app/retriever/hybrid.py†L60-L104】 | Table-driven tests verifying punctuation stripping and ellipsis handling.
| Metadata merge | `_build_result` includes annotations payloads and snippet logic.【F:theo/services/api/app/retriever/hybrid.py†L106-L143】 | Provide fake passage/document objects and annotation DTOs.
| Document ranking | `_apply_document_ranks` assigns ranks and highlights per document.【F:theo/services/api/app/retriever/hybrid.py†L146-L157】 | Validate deterministic ordering and highlight calls.
| Candidate scoring | `_score_candidates` weights lexical/vector/TEI scores, applies osis bonus, and skips zero-score items.【F:theo/services/api/app/retriever/hybrid.py†L160-L213】 | Build `_Candidate` objects with various flag combinations.
| Merge & limit | `_merge_scored_candidates` trims to `k`, computes document max scores, and updates ranks.【F:theo/services/api/app/retriever/hybrid.py†L216-L235】 | Ensure duplicates by document collapse correctly.
| OSIS helpers | `_osis_distance_value` and `_mark_candidate_osis` behave for overlapping/non-overlapping references.【F:theo/services/api/app/retriever/hybrid.py†L248-L267】 | Use deterministic `expand_osis_reference` stubs.
| Guardrail filters | `_passes_author_filter`, `_matches_tradition`, `_matches_topic_domain`, `_passes_guardrail_filters` respect casefolding and missing data.【F:theo/services/api/app/retriever/hybrid.py†L269-L312】 | Parametrise over None/empty values.
| TEI helpers | `_tei_terms` and `_tei_match_score` aggregate list/dict structures and search blobs.【F:theo/services/api/app/retriever/hybrid.py†L315-L341】 | Provide sample metadata dicts with nested values.
| SQL builders | `_build_base_query`, `_build_vector_statement`, `_build_lexical_statement`, `_build_tei_statement` add expected columns and predicates.【F:theo/services/api/app/retriever/hybrid.py†L343-L398】 | Use SQLAlchemy `Compile` with a fake dialect to assert generated SQL fragments without hitting DB.
| Fallback search filters | `_fallback_search` filters by authors, guardrails, OSIS, and lexical/TEI thresholds before scoring.【F:theo/services/api/app/retriever/hybrid.py†L400-L501】 | Replace database session with stub returning scripted rows.
| Postgres hybrid | Branches for vector, lexical, TEI, OSIS pipelines populate `_Candidate` map and respect guardrails.【F:theo/services/api/app/retriever/hybrid.py†L504-L599】 | Use fake session returning iterables; assert candidate map contents.
| Document APIs | `list_documents` pagination, `get_document` missing ID raises, `get_document_passages` totals, `get_latest_digest_document` fallback, `update_document` partial updates, `list_annotations`/`create_annotation`/`delete_annotation` semantics.【F:theo/services/api/app/retriever/documents.py†L37-L200】 | Backed by SQLite test database with fixture data.
| Annotation serialisation | `prepare_annotation_body` rejects empty text, deduplicates passage IDs; `annotation_to_schema` handles JSON and legacy raw text.【F:theo/services/api/app/retriever/annotations.py†L21-L116】 | Include legacy string body and JSON document cases.
| Annotation loading | `load_annotations_for_documents` and `index_annotations_by_passage` skip empty IDs and group correctly.【F:theo/services/api/app/retriever/annotations.py†L118-L150】 | Provide multiple documents with overlapping passage IDs.
| Compose meta | `compose_passage_meta` merges document info with passage meta while preserving overrides.【F:theo/services/api/app/retriever/utils.py†L10-L49】 | Validate that passage metadata wins when keys overlap.

#### 3.2 Integration Tests
| Flow | Scenario | Notes |
|------|----------|-------|
| Hybrid search (vector+lexical) | Seed in-memory Postgres-compatible session (or SQLite with stub vector operations) with passages/documents, run `_postgres_hybrid_search` via dependency injection, and assert combined ranking order. | Use fake embedding service returning deterministic vectors to avoid pgvector dependency.
| Hybrid OSIS-only | Provide OSIS references to ensure `_mark_candidate_osis` and `osis_intersects` filter results correctly. | Use stub `expand_osis_reference` returning deterministic sets.
| Document CRUD | Create document + annotations, then exercise `create_annotation`, `list_annotations`, and `delete_annotation` end-to-end to ensure case builder sync called and database state updates. | Transactional fixture resets DB between tests.

#### 3.3 Property Tests
* Hypothesis-driven fuzzing for `prepare_annotation_body` to ensure passage ID deduplication and metadata passthrough regardless of ordering.【F:theo/services/api/app/retriever/annotations.py†L30-L56】
* Generate random guardrail metadata for `_matches_topic_domain` to confirm normalised comparisons remain symmetric.【F:theo/services/api/app/retriever/hybrid.py†L294-L312】

#### 3.4 Observability Assertions
* Trace attribute tests verifying `_annotate_retrieval_span` sets fields for query, filters, cache status, and backend.【F:theo/services/api/app/retriever/hybrid.py†L29-L57】
* Latency metric assertions in `_fallback_search` ensure span attributes record result count and latency.【F:theo/services/api/app/retriever/hybrid.py†L400-L501】

### Progress
* ✅ Implemented `tests/services/api/app/retriever/test_utils.py` to ensure `compose_passage_meta` merges document context with passage overrides while returning `None` when no metadata is available.
* ✅ Added `tests/services/api/app/retriever/test_annotations.py` to cover annotation payload serialisation, legacy body handling, batched loading, and passage indexing helpers.

---

## Implementation Roadmap
1. **Bootstrap fixtures & fakes** – Create reusable fake settings, sessions, and response helpers shared across ingest/retriever tests.
2. **Backfill unit suites** – Prioritise shim coverage (core), orchestrator/pipeline basics (ingest), and annotation utilities (retriever) for quick wins toward 90%.
3. **Layer integration tests** – Once helpers are in place, add orchestrator and hybrid search integration tests to validate cross-module behaviour.
4. **Introduce property-based checks** – After deterministic fixtures exist, layer Hypothesis strategies for metadata and guardrail normalisation to guard against regression drift.
5. **Track coverage growth** – Run `pytest --cov` after each milestone and update the coverage report, ensuring each package crosses the 90% threshold before moving on.

Following this plan will eliminate the three largest blind spots in our backend coverage and establish a reusable testing toolkit for subsequent modules.
