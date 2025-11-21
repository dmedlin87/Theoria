# ADR 0005: Test Marker Consolidation

- Status: Proposed
- Date: 2025-11-21

## Context

The test suite has accumulated 11+ pytest markers (`slow`, `pgvector`, `celery`, `schema`, `contract`, `gpu`, `e2e`, `db`, `network`, `perf`, `flaky`), indicating fragmentation and suggesting a slow/flaky test suite that developers skip locally.

Key concerns:
- The `flaky` marker teaches developers to ignore red builds
- Duplicate markers exist (`perf`/`performance`)
- Multiple markers require database infrastructure but are tracked separately
- Heavy reliance on CI instead of local testing reduces feedback loop quality

## Decision

### Phase 1: Immediate Changes

1. **Remove `flaky` marker entirely** - Tests marked flaky must either be fixed or deleted. Never commit a test that accepts intermittent failure.

2. **Consolidate database-related markers**:
   - Merge `db`, `pgvector`, and `schema` into single `integration` marker
   - All three require database infrastructure, no benefit to separate tracking

3. **Remove duplicate markers**:
   - Keep `perf`, remove `performance` (or vice versa)

### Phase 2: Test Pyramid Inversion

4. **Mock by default for domain tests**:
   - Unit tests for domain logic should mock DB/vector store
   - Reserve `integration` marker for cross-boundary tests only
   - Target: 90% of domain logic tests run without infrastructure

### Resulting Markers

| Marker | Purpose |
|--------|---------|
| `slow` | Long-running tests requiring opt-in |
| `integration` | Tests requiring database/infrastructure |
| `celery` | Celery worker integration |
| `e2e` | End-to-end/system tests |
| `gpu` | GPU runtime required |
| `contract` | Contract-level compatibility |
| `redteam` | Security tests |
| `network` | Tests that reach network if not mocked |
| `perf` | Performance benchmarks |

## Consequences

- Faster local test runs encourage developers to test before pushing
- Clearer marker semantics improve test organization
- Removal of `flaky` forces quality standards
- Reduced marker count simplifies CI configuration
- Initial refactoring effort required to consolidate existing tests

## Implementation

See `docs/planning/PROJECT_IMPROVEMENTS_ROADMAP.md` Priority 4 for migration plan.
