# Test Results Summary - 2025-10-25

## Test Outcome Statistics
- **Passed:** 1320
- **Failed:** 62
- **Skipped:** 78
- **Errors:** 23
- **Warnings:** 15
- **Total Duration:** 515.64s (8:35)

## Warnings Summary
- `app_factory.py`: Deprecated HTTP status code usage
- `httpx._models.py`: Content upload method deprecation
- Multiple deprecated imports from legacy modules

## Slowest Tests (>4s)
| Test | Duration |
|------|----------|
| `test_sqlite_startup_restores_missing_perspective_column` | 30.61s |
| `test_router_shared_spend_across_processes` | 18.57s |
| `test_router_shared_latency_across_processes` | 18.03s |
| `test_repro_enqueue_job_runtime_error` | 7.16s |
| `test_refresh_hnsw_job_endpoint_uses_defaults` | 7.13s |

## Skipped Tests
- 14 contract tests (require `--contract`)
- 55 shim tests (callable not exported)
- 7 schema tests (require `--schema`)
- 1 realtime test (WebSocket issue)
- 2 contradiction engine tests (transformers not installed)

## Critical Failures & Errors
### Failures
- Database facade import issues
- Export functionality failures
- Runtime error handling
- Security test failures
- API endpoint validation failures

### Errors
- RAG pipeline integration
- Workflow span recording
- OWASP prompt refusal tests
- SQL leak guard tests

**Full output available in:** `test_run_2025-10-25.log`
