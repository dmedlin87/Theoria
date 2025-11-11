# Test Coverage Summary

> **Generated:** October 15, 2025  
> **Status:** 🔴 Below Target (28.3% vs 80% goal)

## Quick Stats

```
┌─────────────────────────────────────────────────────┐
│  PYTHON BACKEND COVERAGE                            │
├─────────────────────────────────────────────────────┤
│  Overall:        28.3%  ████████░░░░░░░░░░░░░░░░░   │
│  Target:         80.0%  ████████████████████████    │
│  Gap:            -51.7% (~9,990 lines)              │
├─────────────────────────────────────────────────────┤
│  Lines Covered:  5,477 / 19,334                     │
│  Test Files:     109                                │
│  Test Functions: 522                                │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  FRONTEND COVERAGE                                  │
├─────────────────────────────────────────────────────┤
│  Status:         ⚠️ 2 Test Suites Failing          │
│  Test Files:     47+ (Vitest + Jest)                │
│  E2E Tests:      7 Playwright specs                 │
│  Passing Tests:  38 / 42                            │
└─────────────────────────────────────────────────────┘
```

## Coverage Distribution

### By Coverage Level

| Level | Count | Packages |
|-------|-------|----------|
| 🔴 0% | 5 | core, mcp, retriever.tests, api.tests (2x) |
| 🟡 21-40% | 10 | workers, ai.rag, creators, cli, routes.ai.workflows, ai, intent, ranking, debug, research |
| 🟢 41-60% | 6 | routes, services, db, app, ingest.stages, routes.ai, facades |
| ✅ 61-100% | 11 | models, adapters, domain, application, platform, etc. |

### Critical Packages (Sorted by Impact × Coverage Gap)

| Rank | Package | Coverage | Impact | Priority |
|------|---------|----------|--------|----------|
| 1 | `services.api.app.core` | 0.0% | CRITICAL | 🚨 |
| 2 | `services.api.app.ingest` | 16.2% | VERY HIGH | 🚨 |
| 3 | `services.api.app.retriever` | 12.8% | VERY HIGH | 🚨 |
| 4 | `services.api.app.ai.rag` | 23.4% | VERY HIGH | ⚠️ |
| 5 | `services.api.app.ai` | 25.5% | VERY HIGH | ⚠️ |
| 6 | `services.api.app.mcp` | 0.0% | HIGH | 🚨 |
| 7 | `services.api.app.routes` | 33.4% | HIGH | ⚠️ |

## Files Generated

1. **`COVERAGE_REVIEW.md`** - Comprehensive analysis with metrics and recommendations
2. **`COVERAGE_ACTION_PLAN.md`** - Week-by-week prioritized tasks with templates
3. **`analyze_coverage.py`** - Script to analyze coverage.xml and generate reports

## Quick Commands

```bash
# Run Python tests with coverage
python -m pytest --cov=theo --cov=mcp_server --cov-report=term-missing --cov-report=html

# Analyze coverage
python analyze_coverage.py

# Run frontend tests (after fixing failures)
cd theo/services/web
npm run test:vitest

# Run E2E tests
cd theo/services/web
npm run test:e2e
```

## Immediate Next Steps

### Week 1 Priority

1. **Fix Frontend Tests** (2-4 hours)
   - File: `theo/services/web/tests/components/Toast.vitest.tsx`
   - Issue: Role selector assertions
   - Impact: Unblocks frontend coverage reporting

2. **Add Core Infrastructure Tests** (1-2 days)
   - Package: `theo/infrastructure/api/app/core/` (0% → 80%)
   - Files: database.py, settings.py, runtime.py, secret_migration.py, settings_store.py, version.py
   - Create: `tests/api/core/test_core_infrastructure.py`

3. **Add MCP Tests** (4-8 hours)
   - Package: `theo/infrastructure/api/app/mcp/` (0% → 80%)
   - File: tools.py
   - Create: `tests/mcp_tools/test_api_mcp_integration.py`

### Expected Week 1 Outcome
- ✅ All frontend tests passing
- ✅ 0 packages with 0% coverage
- ✅ Overall coverage: 28.3% → 35%

## Key Insights

### Strengths
- ✅ Domain layer well-tested (81.1%)
- ✅ Application layer well-tested (82.3%)
- ✅ Models extensively tested (89.8%)
- ✅ Comprehensive test infrastructure (109 test files)
- ✅ E2E and contract testing configured

### Weaknesses
- ❌ Core infrastructure untested (0%)
- ❌ MCP integration untested (0%)
- ❌ Ingest pipeline under-tested (16.2%)
- ❌ Search/retrieval under-tested (12.8%)
- ❌ AI/RAG workflows under-tested (~24%)
- ❌ Frontend test failures blocking coverage

### Opportunities
- 📈 Quick wins: Core tests (small files, high impact)
- 📈 Existing fixtures: citations, markdown
- 📈 Contract testing: Schemathesis configured but underutilized
- 📈 Test templates: Strong existing patterns to follow

### Risks
- ⚠️ Core functionality changes could break production
- ⚠️ RAG quality issues may go undetected
- ⚠️ API contract violations possible
- ⚠️ Performance regressions untracked

## Coverage Trend (Projected)

```
100% │                                          ╱─── Goal (80%)
     │                                       ╱─┘
 80% │                                    ╱─┘
     │                                 ╱─┘
 60% │                              ╱─┘
     │                           ╱─┘
 40% │                        ╱─┘
     │                    ╱──┘
 20% │            ╱──────┘
     │    ╱──────┘
  0% └────┴────┴────┴────┴────┴────┴────┴────
      Now  W1  W2  W3  W4  W5  W6  W7  W8
    28.3% 35% 40% 45% 50% 60% 70% 75% 80%
```

## Test Quality Checklist

### Current State
- [x] Unit tests exist
- [x] Integration tests exist
- [x] E2E tests configured (Playwright)
- [x] Contract tests configured (Schemathesis)
- [x] Coverage tracking enabled
- [ ] Coverage gates in CI (disabled)
- [ ] Branch coverage tracked (not enabled)
- [ ] Mutation testing
- [ ] Performance benchmarks
- [ ] Load testing

### Target State (8 weeks)
- [x] All checkboxes above
- [x] 80% overall coverage
- [x] 0 packages below 50%
- [x] CI gates enforcing coverage
- [x] Automated quality reports

## Related Documentation

- **Detailed Analysis:** `COVERAGE_REVIEW.md`
- **Action Plan:** `COVERAGE_ACTION_PLAN.md`
- **Pytest Config:** `pyproject.toml` (lines 89-106)
- **Frontend Config:** `theo/services/web/vitest.config.ts`
- **CI Workflows:** `.github/workflows/ci.yml`

## Team Resources

### Getting Started
1. Read `COVERAGE_REVIEW.md` for context
2. Review `COVERAGE_ACTION_PLAN.md` for specific tasks
3. Check test templates in action plan
4. Look at existing tests for patterns

### Getting Help
- Existing tests: `tests/` directory (109 files, 522 functions)
- Fixtures: `fixtures/` directory
- Shared setup: `tests/conftest.py`
- Test markers: `pyproject.toml` lines 95-100

---

**Status Update Schedule:** Every Monday @ 9am  
**Full Review Schedule:** After each phase completion  
**Owner:** Engineering Team  
**Last Updated:** October 15, 2025
