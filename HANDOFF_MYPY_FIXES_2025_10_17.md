# Handoff: MyPy Type Error Fixes

**Session Date:** October 17, 2025  
**Last Update:** October 17, 2025 (Quick Wins Complete)  
**Objective:** Fix all mypy errors reported in CI  
**Status:** ✅ Major Progress - Infrastructure Complete, 1678 errors remaining (down from ~2000+)

---

## 🎯 What Was Accomplished

### 1. Type Stub Files Updated (.pyi files)

Complete overhaul of type stub files to match actual model implementations:

#### `typings/theo/services/api/app/db/models.pyi`
**Added missing attributes to `Document` class:**
- `authors: list[str] | None`
- `doi`, `venue`, `year`, `theological_tradition`, `topic_domains`
- `sha256`, `storage_path`, `enrichment_version`, `provenance_score`
- `channel`, `video_id`, `duration_seconds`, `bib_json`, `pub_date`
- `passages`, `annotations` relationships

**Added missing model classes (previously causing "has no attribute" errors):**
- ✅ `Passage` - Full class definition with all attributes
- ✅ `PassageVerse` - Association table model
- ✅ `DocumentAnnotation` - Annotations model
- ✅ `Creator`, `CreatorClaim` - Creator-related models
- ✅ `Video` - Video metadata model
- ✅ `TranscriptSegment`, `TranscriptSegmentVerse` - Transcript models
- ✅ `TranscriptQuote`, `TranscriptQuoteVerse` - Quote models
- ✅ `FeedbackEventAction` - Enum for feedback actions
- ✅ `ContradictionSeed`, `HarmonySeed`, `CommentaryExcerptSeed` - Seed models
- ✅ `CaseObjectType`, `CaseSource`, `CaseObject` - Case builder models

#### `typings/theo/services/api/app/models/search.pyi`
**Enhanced `HybridSearchRequest`:**
- Added `cursor: str | None`
- Added `limit: int | None`
- Added `mode: str`

**Enhanced `HybridSearchResult`:**
- Added `text: str`, `raw_text: str | None`
- Added `rank: int`
- Added score fields: `document_score`, `document_rank`, `lexical_score`, `vector_score`, `osis_distance`
- Added `model_dump()` method

**Enhanced `HybridSearchFilters`:**
- Added `model_dump()` method

#### `typings/theo/services/api/app/models/verses.pyi`
**Added missing verse-related models:**
- ✅ `VerseMention` - Mention model with passage and context
- ✅ `VerseGraphNode` - Graph node representation
- ✅ `VerseGraphEdge` - Graph edge with relationship types
- ✅ `VerseGraphFilters` - Filtering for graph queries
- ✅ `VerseGraphResponse` - Complete graph response
- ✅ `VerseTimelineBucket` - Timeline aggregation
- ✅ `VerseTimelineResponse` - Timeline response

---

### 2. Removed Unused Type: Ignore Comments (12 instances)

**Files cleaned:**
- ✅ `theo/services/api/app/ingest/stages/base.py` - telemetry import
- ✅ `theo/services/api/app/ingest/stages/enrichers.py` - context parameter (2 classes)
- ✅ `theo/services/api/app/ingest/stages/persisters.py` - context parameter (2 classes)
- ✅ `theo/services/api/app/ingest/stages/parsers.py` - context parameter (4 classes)
- ✅ `theo/services/api/app/ingest/stages/fetchers.py` - context parameter (3 classes)
- ✅ `theo/services/api/app/ingest/parsers.py` - HTMLParser overrides (3 methods)
- ✅ `theo/services/api/app/ingest/network.py` - redirect_request override
- ✅ `theo/services/api/app/ingest/pipeline.py` - _UrlDocumentPersister.persist
- ✅ `theo/services/api/app/case_builder/ingest.py` - meta dict access

---

### 3. Added Missing Type Annotations

**Ingestion Pipeline Stages:**
- All `parse()`, `persist()`, `fetch()`, `enrich()` methods now have proper signatures
- Changed from `def method(self, *, context, state: dict[str, Any])` 
- To: `def method(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]`

**Network Module (`theo/services/api/app/ingest/network.py`):**
- `ensure_url_allowed(settings: Any, url: str) -> None`
- `ensure_resolved_addresses_allowed(settings: Any, addresses: tuple[IPAddress, ...]) -> None`
- `fetch_web_document(settings: Any, url: str, *, opener_factory: Any = build_opener) -> tuple[str, dict[str, str | None]]`
- `resolve_fixtures_dir(settings: Any) -> Path | None`
- `LoopDetectingRedirectHandler.redirect_request(req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any`

**HTML Parser (`theo/services/api/app/ingest/parsers.py`):**
- `handle_starttag(tag: str, attrs: list[tuple[str, str | None]]) -> None`
- `handle_endtag(tag: str) -> None`
- `handle_data(data: str) -> None`

**Helper Functions (`theo/services/api/app/ingest/stages/persisters.py`):**
- `_set_chunk_metrics(context: Any, parser_result: Any) -> None`

**Case Builder (`theo/services/api/app/case_builder/ingest.py`):**
- `_passage_meta(passage: Passage) -> dict[str, Any] | None`
- `_source_meta(document: Document) -> dict[str, Any] | None`
- Added `from typing import Any`

---

### 4. Fixed Module Export Issues

**`theo/services/api/app/ingest/osis.py`:**
```python
__all__ = [
    "expand_osis_reference",
    "format_osis",
    "osis_to_readable",
    "DetectedOsis",
    "combine_references",
    "detect_osis_references",
    "canonical_verse_range",
    "osis_intersects",
    "classify_osis_matches",
]
```
- Fixed: `Module "theo.services.api.app.ingest.osis" does not explicitly export attribute "expand_osis_reference"`

**`theo/services/api/app/routes/export.py`:**
```python
__all__ = ["router", "api_router", "ExportError"]
```
- Fixed: Test imports of `ExportError` now work

---

### 5. Quick Wins Completed (Latest Session)

**Files Modified:**
- ✅ `theo/services/api/app/ai/reasoning/chain_of_thought.py` - Added `Any` import, typed 5 `dict` parameters to `dict[str, Any]`
- ✅ `theo/services/api/app/enrich/metadata.py` - Removed unreachable code (2 instances), added `Settings` type annotation to `__init__`
- ✅ `theo/services/api/app/db/verse_graph.py` - Added type annotations to `_range_condition()` function

**Dependency Installed:**
- ✅ `types-cachetools` - Fixes 1 import-untyped error

**Errors Fixed:** 18 total
- `type-arg` errors: ~5 fixed (bare `dict` → `dict[str, Any]`)
- `unreachable` errors: 2 fixed (redundant isinstance checks removed)
- `no-untyped-def` errors: 2 fixed (added function annotations)
- `import-untyped` errors: 1 fixed (types-cachetools installed)

**New Baseline:** 1678 errors (down from 1696)

---

## 📊 Current Status

### MyPy Results
```
Found 1678 errors in 69 files (checked 39 source files)
```

**Progress:** 
- Initial: ~2000+ errors
- After infrastructure work: 1696 errors (71 files)
- After quick wins: 1678 errors (69 files) ⬇️ **18 errors fixed**

### Error Categories Remaining

1. **`no-any-return`** (~50+ instances)
   - Functions declared to return specific types but returning `Any`
   - Primarily in: `theo/services/api/app/ai/clients.py`
   - Examples: Functions returning `str` but extracting from untyped JSON

2. **`type-arg`** (~10 instances) ⬇️ _5 fixed_
   - Missing type parameters for generic types
   - `dict` → `dict[str, Any]`
   - `set` → `set[str]`
   - `list` → `list[str]`
   - Remaining files need review

3. **`unreachable`** (~3 instances) ⬇️ _2 fixed_
   - Unreachable code statements
   - Remaining: Check `theo/services/api/app/ai/clients.py`

4. **`attr-defined`** (~10 instances)
   - Pydantic model methods not recognized (e.g., `model_dump`, `model_rebuild`)
   - Document construction issues
   - Files: `theo/services/api/app/models/documents.py`, `theo/services/api/app/analytics/telemetry.py`

5. **`name-defined`** (~3 instances)
   - Undefined names: `RAGAnswer`
   - File: `theo/services/api/app/ai/rag/cache.py`

6. **`call-arg`** (~5 instances)
   - Unexpected keyword arguments
   - Document/model constructor mismatches
   - Files: `theo/services/api/app/analytics/topics.py`, `theo/services/api/app/routes/export.py`

7. **`no-untyped-def`** (~1 instance) ⬇️ _2 fixed_
   - Functions missing type annotations
   - Remaining: Check `theo/services/api/app/services/ingestion_service.py:288`

8. **`import-untyped`** ✅ _RESOLVED_
   - ~~Missing stub for `cachetools` library~~
   - Fixed: `types-cachetools` installed

9. **`assignment`** (~2 instances)
   - Incompatible type assignments
   - File: `theo/services/api/app/ai/clients.py`

---

## 🗂️ Files Modified

### Type Stub Files (Complete Rewrites)
1. `typings/theo/services/api/app/db/models.pyi` - **143 lines** (was 26 lines)
2. `typings/theo/services/api/app/models/search.pyi` - Added attributes and methods
3. `typings/theo/services/api/app/models/verses.pyi` - **83 lines** (was 13 lines)

### Source Files (Type Annotations Added)
4. `theo/services/api/app/ingest/stages/base.py`
5. `theo/services/api/app/ingest/stages/enrichers.py`
6. `theo/services/api/app/ingest/stages/persisters.py`
7. `theo/services/api/app/ingest/stages/parsers.py`
8. `theo/services/api/app/ingest/stages/fetchers.py`
9. `theo/services/api/app/ingest/parsers.py`
10. `theo/services/api/app/ingest/network.py`
11. `theo/services/api/app/ingest/pipeline.py`
12. `theo/services/api/app/ingest/osis.py`
13. `theo/services/api/app/case_builder/ingest.py`
14. `theo/services/api/app/routes/export.py`

---

## 🗂️ Files Modified (This Session)

### Quick Wins Completed
1. ✅ `theo/services/api/app/ai/reasoning/chain_of_thought.py` - Generic type parameters
2. ✅ `theo/services/api/app/enrich/metadata.py` - Unreachable code removed, type annotations added
3. ✅ `theo/services/api/app/db/verse_graph.py` - Function type annotations
4. ✅ Installed: `types-cachetools`

---

## 🚀 Next Steps (Priority Order)

### High Priority (Remaining Quick Wins)

1. **Find Remaining Generic Type Parameters** (~10 errors)
   - Search codebase for bare `dict`, `set`, `list` without type parameters
   - Focus on API modules under strict typing rules

2. **Check Remaining Unreachable Code** (~3 errors)
   - `theo/services/api/app/ai/clients.py` - may have remaining instances

3. **Add Missing Function Annotation** (~1 error)
   - `theo/services/api/app/services/ingestion_service.py:288`

### Medium Priority (More Complex)

5. **Fix `no-any-return` Errors** (~50 errors)
   - **Strategy:** Add explicit type casts or assertions
   - **Primary file:** `theo/services/api/app/ai/clients.py`
   - **Pattern:** Functions extracting from untyped JSON/dicts
   - **Solution examples:**
     ```python
     # Before
     def get_value(data: dict) -> str:
         return data["key"]  # error: Returning Any from function declared to return "str"
     
     # After
     def get_value(data: dict[str, Any]) -> str:
         value = data["key"]
         if not isinstance(value, str):
             raise ValueError("Expected string")
         return value
     ```

6. **Fix Pydantic Model Issues** (~10 errors)
   - Update stub files or add `# type: ignore` for Pydantic magic methods
   - Files: `theo/services/api/app/models/documents.py`, `theo/services/api/app/analytics/telemetry.py`
   - Issue: `model_dump`, `model_rebuild` not recognized on Pydantic models in stubs

7. **Fix Document Constructor Calls** (~5 errors)
   - `theo/services/api/app/analytics/topics.py:230` - Multiple unexpected keyword arguments
   - Need to check actual `Document` model vs stub definition for constructor
   - May need to update stub file `__init__` signature

### Low Priority (Documentation/Cleanup)

8. **Define Missing Names**
   - `RAGAnswer` in `theo/services/api/app/ai/rag/cache.py:129`
   - Likely needs import or class definition

9. **Fix Assignment Incompatibilities**
   - `theo/services/api/app/ai/clients.py:838, 849`
   - Assigning `str | None` to `str` variables

---

## ⚠️ Important Notes

### MyPy Configuration
The project uses **strict typing** for specific modules defined in `mypy.ini`:
```ini
[mypy-theo.services.api.app.*]
disallow_untyped_defs = True
disallow_incomplete_defs = True

[mypy-theo.services.api.app.routes.*]
disallow_untyped_defs = True
disallow_incomplete_defs = True

[mypy-theo.services.api.app.models.*]
disallow_untyped_defs = True
disallow_incomplete_defs = True
```

Many remaining errors are in modules **not** covered by strict typing rules (e.g., AI/RAG modules). Consider whether to extend strict typing to these areas.

### Type Stub Philosophy
- Stub files (`.pyi`) should mirror the **runtime** structure of models
- They exist in `typings/` directory
- Key stub files now accurately reflect `theo.adapters.persistence.models` exports

### Testing After Changes
Run mypy to verify changes:
```powershell
python -m mypy --config-file mypy.ini
```

**Baselines:**
- Previous: 1696 errors in 71 files
- Current: **1678 errors in 69 files** ⬇️ 18 errors fixed

---

## 🔍 Key Patterns for Future Fixes

### Pattern 1: Stage Method Signatures
```python
# All ingestion stage methods should use this signature:
def method_name(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
    ...
```

### Pattern 2: Generic Type Annotations
```python
# Always use typed generics
payload: dict[str, Any] = {}
tags: list[str] = []
visited: set[str] = set()
```

### Pattern 3: Optional Dependency Imports
```python
# Keep type: ignore for optional dependencies
try:
    import optional_lib
except ImportError:
    optional_lib = None  # type: ignore[assignment]
```

### Pattern 4: Pydantic Model Methods
```python
# If stub doesn't have model_dump, add it:
class MyModel:
    ...
    def model_dump(self, **kwargs: object) -> dict[str, object]: ...
```

---

## 📝 References

### Related Documentation
- `mypy.ini` - MyPy configuration
- `typings/` - Type stub directory
- `theo/adapters/persistence/models.py` - Source of truth for ORM models

### Key Commits in This Session
- Updated all type stub files for database models
- Added type annotations to ingestion pipeline stages
- Fixed module export issues for `expand_osis_reference` and `ExportError`
- Cleaned up unused `type: ignore` comments

---

## ✅ Session Completion Checklist

**Infrastructure (Initial Session):**
- [x] Type stubs updated for all database models
- [x] Ingestion pipeline stages properly typed
- [x] Module exports fixed
- [x] Unused type: ignore comments removed
- [x] Documentation created (this file)

**Quick Wins (Latest Session):**
- [x] Install missing type stubs (`types-cachetools`)
- [x] Fix generic type parameters in chain_of_thought.py (5 instances)
- [x] Remove unreachable code in metadata.py (2 instances)
- [x] Add missing function type annotations (2 functions)

**Still TODO:**
- [ ] Find and fix remaining ~10 generic type parameters
- [ ] Address ~50 `no-any-return` errors
- [ ] Fix Pydantic model stub issues (~10 errors)
- [ ] Fix Document constructor call-arg errors (~5 errors)

---

**Next Agent/Developer:** Start with "High Priority" quick wins above. The foundation is solid - remaining errors are mostly straightforward typing improvements. Good luck! 🚀
