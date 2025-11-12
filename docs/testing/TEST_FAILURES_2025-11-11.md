# Test Failures Report - November 11, 2025

**Summary**: 79 failed, 1434 passed, 126 skipped, 17 warnings, 100 errors in 422.27s

---

## Critical Issues

### 1. Embedding Service Stub Not Patched

**Impact**: High - Breaks 7+ bootstrap and application initialization tests

**Root Cause**:
- `resolve_application()` in `theo/application/services/bootstrap.py:273` calls `_build_embedding_rebuild_service()`
- This invokes `get_embedding_service()` at line 256
- The stub at `tests/commands/test_embedding_rebuild.py:131` raises `RuntimeError: embedding service stub should be patched`
- Tests are not properly mocking this service before calling `resolve_application()`

**Affected Tests**:
```
tests/application/services/test_bootstrap.py::test_resolve_application_registers_environment_adapters
tests/application/services/test_bootstrap.py::test_resolve_application_wires_container
tests/application/services/test_bootstrap.py::test_resolve_application_caches_results
tests/application/services/test_bootstrap.py::test_restart_reinitializes_bootstrap
tests/services/test_services_bootstrap.py::test_resolve_application_results_are_cached
tests/services/test_services_bootstrap.py::test_research_service_factory_binds_sqlalchemy_repositories
tests/services/test_services_bootstrap.py::test_resolve_application_returns_container_and_registry
```

**Stack Trace**:
```python
theo\application\services\bootstrap.py:273: in resolve_application
    embedding_rebuild_service = _build_embedding_rebuild_service()
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
theo\application\services\bootstrap.py:256: in _build_embedding_rebuild_service
    embedding_service = get_embedding_service()
                        ^^^^^^^^^^^^^^^^^^^^^^^
tests\commands\test_embedding_rebuild.py:131: RuntimeError
    raise RuntimeError("embedding service stub should be patched")
```

**Recommended Fix**:
- Add fixture or setup to patch `get_embedding_service()` in all bootstrap tests
- Consider making embedding service optional in `resolve_application()`
- Or inject embedding service as a dependency rather than calling global function

---

### 2. URL Ingestion 404 Handling

**Impact**: Medium - Expected behavior but logged as errors in test runs

**Root Cause**:
- Tests attempting to fetch `https://example.com/test` receive HTTP 404
- `fetch_web_document()` in `theo/infrastructure/api/app/ingest/network.py:234` catches and wraps as `UnsupportedSourceError`

**Error Flow**:
```
urllib.request.py:639 → HTTPError: HTTP Error 404
  ↓
ingest/network.py:234 → UnsupportedSourceError("Unable to fetch URL: https://example.com/test")
  ↓
ingest/orchestrator.py:64 → Propagated through pipeline
  ↓
workers/tasks.py:502 → Logged at task level
```

**Stack Trace**:
```python
File "network.py", line 213, in fetch_web_document
    response = opener.open(request, timeout=timeout)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "urllib/request.py", line 639, in http_error_default
    raise HTTPError(req.full_url, code, msg, hdrs, fp)
urllib.error.HTTPError: HTTP Error 404: Not Found

# Wrapped as:
File "network.py", line 234, in fetch_web_document
    raise UnsupportedSourceError(f"Unable to fetch URL: {url}") from exc
```

**Affected Code Paths**:
- `theo/infrastructure/api/app/ingest/network.py:213-234`
- `theo/infrastructure/api/app/ingest/pipeline.py:190`
- `theo/infrastructure/api/app/ingest/stages/fetchers.py:113`
- `theo/infrastructure/api/app/workers/tasks.py:502,516`

**Recommendation**:
- This appears to be working as designed (error handling is correct)
- Consider using mock HTTP responses in tests to avoid real network calls
- Suppress expected error logs in test environment

---

## Test Failure Categories

### Category A: Database/SQLAlchemy Issues (18 failures)

**Tests**:
```
- test_run_sql_migrations_skips_existing_sqlite_column
- test_run_sql_migrations_reapplies_when_ledger_stale
- test_seeders_remove_stale_records
- test_api_boots_contradiction_seeding_without_migrations
- test_watchlist_forbidden_without_subject
- test_watchlist_requires_authentication
- test_list_watchlists_filters_by_principal_subject
- test_create_watchlist_assigns_principal_subject
- test_other_user_watchlist_returns_not_found
```

**Common Pattern**: SQLAlchemy session/engine configuration issues in test fixtures

---

### Category B: Worker Task Failures (13 failures)

**Tests**:
```
tests/workers/test_tasks.py::*
tests/workers/test_tasks_optimized.py::*
tests/workers/test_tasks_perf_patch.py::*
```

**Common Issues**:
- Job tracking/status updates
- Document ingestion pipeline
- Citation validation
- Performance metrics

---

### Category C: API Route Errors (100+ errors)

**Major Areas**:
- AI error responses (`tests/api/test_ai_error_responses.py` - 4 errors)
- Citation export (`tests/api/test_ai_citation_export.py` - 9 errors)
- Notebooks (`tests/api/test_notebooks.py` - 5 errors)
- Zotero export (`tests/api/test_export_zotero_route.py` - 10 errors)
- Dashboard (`tests/api/test_dashboard_route.py` - 2 errors)
- GraphQL schema (`tests/api/test_graphql_schema.py` - 8 errors)
- Red team tests (`tests/redteam/test_ai_redteam.py` - 19 errors)
- Workflow spans (`tests/api/test_workflow_spans.py` - 4 errors)

**Pattern**: Most appear to be import/dependency issues in test setup

---

### Category D: Architecture Boundary Violations (7 failures)

**Tests**:
```
tests/application/test_application_boundaries.py::test_application_layer_does_not_depend_on_services[module_path44-55]
tests/architecture/test_module_boundaries.py::test_platform_package_removed
tests/architecture/test_dto_boundaries.py::*
```

**Issue**: Application layer importing from infrastructure/services layers

**Affected Modules** (from test parameters):
- `module_path44`, `module_path46`, `module_path47`, `module_path48`, `module_path49`, `module_path51`, `module_path55`

---

### Category E: Evidence/Research Domain (5 failures)

**Tests**:
```
- test_get_verse_graph_builds_nodes_edges_and_filters
- test_preview_evidence_card_rolls_back
- test_generate_research_note_preview_does_not_persist
- test_create_research_note_commit_persists
- test_chat_session_quality_gates_reject_invalid_mode
- test_chat_session_quality_gates_reject_long_messages
```

---

### Category F: CLI/Command Failures (4 failures)

**Tests**:
```
tests/cli/test_refresh_hnsw_cli.py::*
tests/commands/test_embedding_rebuild.py::*
```

**Issue**: Command-line interface tests failing due to service mocking issues

---

### Category G: Integration Test Failures (4 failures)

**Tests**:
```
- test_biblical_analysis_workflow_end_to_end
- test_audio_pipeline_full
- test_ingest_batch_via_api_routes_items
- test_duplicate_file_ingest_returns_400
- test_duplicate_url_ingest_returns_400
```

---

## Warnings (17 total)

### Deprecation Warnings

1. **testcontainers** - `@wait_container_is_ready` decorator deprecated *(resolved)*
   - Location: `.venv\Lib\site-packages\testcontainers\core\waiting_utils.py:215`
   - Resolution: Attach `LogMessageWaitStrategy("database system is ready to accept connections")`
     when provisioning the Postgres Testcontainer (`tests/fixtures/pgvector.py`).

2. **datetime.utcnow()** deprecated
   - Location: `theo\adapters\biblical_ai_processor.py:93`
   - Recommendation: Use `datetime.now(datetime.UTC)`

3. **Module import deprecations** - Old import paths deprecated
   - `theo.infrastructure.api.app.core.version` → `theo.application.facades.version`
   - `theo.infrastructure.api.app.core.database` → `theo.application.facades.database`
   - `theo.infrastructure.api.app.core.settings_store` → `theo.application.facades.settings_store`
   - `theo.infrastructure.api.app.core.settings` → `theo.application.facades.settings`
   - `theo.infrastructure.api.app.core.runtime` → `theo.application.facades.runtime`
   - `theo.infrastructure.api.app.core.secret_migration` → `theo.application.facades.secret_migration`

4. **pytest-celery warning**
   - `celery.contrib.pytest` module already imported, cannot be rewritten

---

## Skipped Tests (126 total)

### By Category:

- **Contract tests** (@contract marker): 15 skipped
  - Requires `--contract` opt-in flag

- **PGVector tests** (@pgvector marker): ~45 skipped
  - Requires `--pgvector` opt-in flag
  - Tests involving vector database operations

- **Schema tests** (@schema marker): ~10 skipped
  - Requires `--schema` opt-in flag

- **Shim tests**: 55 skipped
  - Callables not exported by shims

---

## Priority Actions

### Immediate (P0)
1. **Fix embedding service stub patching** in bootstrap tests
   - Add global fixture or conftest setup
   - Patch `get_embedding_service()` before any `resolve_application()` calls

### High Priority (P1)
2. **Resolve architecture boundary violations** (7 failures)
   - Audit application layer imports
   - Move violating code to appropriate layers

3. **Fix worker task failures** (13 failures)
   - Review task isolation and mocking strategy
   - Ensure job tracking is properly mocked

### Medium Priority (P2)
4. **Address API route test errors** (100 errors)
   - Likely cascading from bootstrap issues
   - May auto-resolve after P0 fix

5. **Update deprecated datetime usage**
   - Replace `datetime.utcnow()` with `datetime.now(datetime.UTC)`

### Low Priority (P3)
6. **Update testcontainers usage**
   - ✅ Structured wait strategies applied in `tests/fixtures/pgvector.py`

7. **Clean up import deprecation warnings**
   - Already using facade pattern, may be from test imports

---

## Test Statistics

- **Total Tests**: 1,639
- **Passed**: 1,434 (87.5%)
- **Failed**: 79 (4.8%)
- **Errors**: 100 (6.1%)
- **Skipped**: 126 (7.7%)
- **Runtime**: 422.27s (7 minutes 2 seconds)

### Slowest Tests (>100s)
- `test_sqlite_startup_restores_missing_perspective_column`: 130.74s
- `test_router_shared_spend_across_processes`: 19.52s
- `test_router_shared_latency_across_processes`: 19.36s

---

## Investigation Notes

### Possible Root Causes

1. **Test Isolation Issues**: Bootstrap state leaking between tests
2. **Missing Fixtures**: Embedding service not properly mocked globally
3. **Database State**: SQLite migrations/seeds may not be properly reset
4. **Import Order**: Circular dependencies or import-time side effects

### Next Steps

1. Run individual test files to isolate failures
2. Check if `conftest.py` has proper teardown/setup
3. Review recent changes to `bootstrap.py` and embedding service
4. Verify test database fixtures are properly isolated

---

## Related Files

### Source Files
- `theo/application/services/bootstrap.py:256,273`
- `theo/infrastructure/api/app/ingest/network.py:213,234`
- `theo/infrastructure/api/app/ingest/pipeline.py:190,206`
- `theo/infrastructure/api/app/workers/tasks.py:502,516`
- `theo/adapters/biblical_ai_processor.py:93`

### Test Files
- `tests/commands/test_embedding_rebuild.py:131`
- `tests/application/services/test_bootstrap.py`
- `tests/services/test_services_bootstrap.py`
- `tests/workers/test_tasks.py`
- `tests/api/**/*.py` (multiple)

---

**Generated**: November 11, 2025 at 6:30pm UTC-06:00
