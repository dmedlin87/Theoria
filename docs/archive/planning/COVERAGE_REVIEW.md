# Test Coverage Review

**Date:** October 15, 2025  
**Reviewer:** Automated Analysis

## Executive Summary

- **Python Backend Coverage:** 28.3% (5,477/19,334 lines)
- **Target Coverage:** 80%
- **Gap:** ~9,990 lines needed to reach target
- **Frontend Tests:** Present but with 2 failing test suites

---

## Backend Coverage Analysis

### Overall Metrics
```
Total Lines:     19,334
Covered Lines:    5,477
Coverage Rate:    28.3%
Branch Coverage:  Not tracked
```

### Critical Gaps

#### Packages with 0% Coverage (5 packages)
🚨 **HIGH PRIORITY - No test coverage whatsoever:**

1. `services.api.app.core` - 7 files
2. `services.api.app.mcp` - 2 files
3. `services.api.app.retriever.tests` - 2 files
4. `services.api.tests` - 23 files
5. `services.api.tests.workers` - 2 files

#### Packages Below 20% Coverage (14 packages)
⚠️ **MEDIUM-HIGH PRIORITY - Critically low coverage:**

| Package | Coverage | Files | Priority |
|---------|----------|-------|----------|
| `services.api.app.transcripts` | 11.8% | 2 | High |
| `services.api.app.retriever` | 12.8% | 8 | High |
| `services.geo` | 14.1% | 2 | Medium |
| `services.api.app.notebooks` | 14.6% | 1 | Medium |
| `services.api.app.export` | 15.5% | 3 | Medium |
| `services.api.app.ingest` | 16.2% | 13 | High |
| `services.api.app.enrich` | 16.4% | 2 | Medium |
| `services.api.app.analytics` | 17.9% | 4 | Medium |
| `services.api.app.workers` | 18.4% | 2 | Medium |

#### Packages Below 30% Coverage (10 additional packages)
📊 **MEDIUM PRIORITY - Below acceptable threshold:**

| Package | Coverage | Files |
|---------|----------|-------|
| `services.api.app.ai.rag` | 23.4% | 10 |
| `services.api.app.creators` | 23.5% | 3 |
| `services.cli` | 24.1% | 1 |
| `services.api.app.routes.ai.workflows` | 24.8% | 9 |
| `services.api.app.ai` | 25.5% | 9 |
| `services.api.app.intent` | 27.0% | 2 |
| `services.api.app.ranking` | 27.1% | 4 |
| `services.api.app.debug` | 27.3% | 3 |

### Well-Tested Packages
✅ **Areas with strong coverage:**

| Package | Coverage | Files |
|---------|----------|-------|
| `services.api.app.models` | 89.8% | 15 |
| `adapters` | 93.8% | 2 |
| `domain` | 81.1% | 3 |
| `application` | 82.3% | 3 |
| `application.facades` | 54.3% | 7 |
| `services.api.app.routes.ai` | 53.8% | 3 |

---

## Frontend Coverage Analysis

### Test Infrastructure
- **Framework:** Vitest + Jest
- **Test Files:** 47+ test files found
- **E2E Tests:** Playwright (7 spec files)
- **Coverage Target:** 80% (lines, functions, statements, branches)

### Test Status
```
Test Suites:  2 failed | 9 passed (11 total)
Tests:        4 failed | 38 passed (42 total)
Duration:     5.14s
```

### Failed Tests
⚠️ **Frontend test failures preventing coverage generation:**
- `tests/components/Toast.vitest.tsx` - Role selector issues

### Frontend Test Categories
1. **Component Tests:** Toast, Icon, ErrorBoundary, Pagination, LoadingStates, SearchFilters
2. **Feature Tests:** Chat workspace, Upload page, Search page, Settings page
3. **Hook Tests:** useSearchFilters, workflow hooks, session restoration
4. **E2E Tests:** Accessibility, journeys, search, UI, verse graph, visual regression
5. **Integration Tests:** API routes, document client, chat client

---

## Recommendations

### Immediate Actions (Week 1)

1. **Fix Frontend Test Failures**
   - Resolve Toast component test issues
   - Generate frontend coverage baseline
   - Target: All tests passing

2. **Address Zero-Coverage Packages**
   - `services.api.app.core`: Core functionality should have tests
   - `services.api.app.mcp`: MCP server tools need coverage
   - Add basic smoke tests for all zero-coverage packages

### Short-term Goals (Month 1)

3. **Boost Critical Low-Coverage Areas**
   - `services.api.app.ingest` (16.2% → 60%+): 13 files, critical path
   - `services.api.app.retriever` (12.8% → 60%+): 8 files, search functionality

4. **AI/RAG Coverage**
   - `services.api.app.ai.rag` (23.4% → 70%+): Core AI functionality
   - `services.api.app.ai` (25.5% → 70%+): AI orchestration
   - Add integration tests for RAG pipelines

5. **API Routes**
   - `services.api.app.routes` (33.4% → 70%+): API surface
   - `services.api.app.routes.ai.workflows` (24.8% → 70%+): Workflow endpoints

### Medium-term Goals (Quarter 1)

6. **Establish Coverage Gates**
   - Enable `--cov-fail-under=80` in CI/CD
   - Require 80%+ coverage for new code
   - Progressive increase: 40% → 60% → 80%

7. **Integration Test Suite**
   - End-to-end workflow tests
   - Database migration tests
   - API contract tests (Schemathesis already configured)

8. **Security Testing**
   - Red team tests (markers exist but coverage unknown)
   - Input validation tests
   - Authentication/authorization tests

### Long-term Improvements (Ongoing)

9. **Test Quality**
   - Add branch coverage tracking
   - Mutation testing for critical paths
   - Property-based testing for complex logic

10. **Documentation**
    - Testing guidelines in CONTRIBUTING.md
    - Coverage requirements per module type
    - Example test patterns

---

## Coverage Improvement Plan

### Phase 1: Foundation (Weeks 1-2)
- [ ] Fix frontend test suite
- [ ] Generate baseline coverage reports
- [ ] Add tests for zero-coverage packages (basic smoke tests)
- [ ] Target: 35% overall coverage

### Phase 2: Critical Paths (Weeks 3-6)
- [ ] Ingest pipeline tests
- [ ] Retriever/search tests
- [ ] AI/RAG workflow tests
- [ ] API route tests
- [ ] Target: 50% overall coverage

### Phase 3: Comprehensive Coverage (Weeks 7-12)
- [ ] Feature completeness tests
- [ ] Edge case coverage
- [ ] Integration tests
- [ ] Target: 70% overall coverage

### Phase 4: Quality & Maintenance (Ongoing)
- [ ] Enable coverage gates in CI
- [ ] Regular coverage reviews
- [ ] Maintain 80%+ coverage
- [ ] Target: 80% overall coverage

---

## Test Execution Commands

### Python Backend
```bash
# Run all tests with coverage
python -m pytest --cov=theo --cov=mcp_server --cov-report=term-missing --cov-report=html --cov-report=xml

# Run specific package tests
python -m pytest tests/api/test_ingest.py --cov=theo.services.api.app.ingest

# Generate coverage report
python analyze_coverage.py
```

### Frontend
```bash
cd theo/services/web

# Unit tests with coverage
npm run test:vitest

# E2E tests
npm run test:e2e

# Accessibility tests
npm run test:a11y

# Quality gates
npm run quality:gates
```

---

## Metrics to Track

1. **Overall Coverage Trend** (weekly)
   - Python: Currently 28.3%
   - Frontend: TBD (blocked by test failures)

2. **Package Coverage Distribution** (biweekly)
   - Packages below 50%: 29 currently
   - Packages at 0%: 5 currently

3. **Test Count Growth** (monthly)
   - Current: 522 Python tests, 42 Frontend tests

4. **Test Execution Time** (weekly)
   - Current: Frontend ~5s, Python TBD

5. **Failed Test Count** (daily)
   - Current: 2 frontend test suites failing

---

## Notes

- **Test discovery:** 109 Python test files with 522 test functions
- **Coverage tools:** pytest-cov (Python), vitest + coverage-v8 (Frontend)
- **CI/CD:** Coverage disabled by default for faster test discovery
- **Red team tests:** Markers exist (`@redteam`) but execution status unknown
- **Contract tests:** Schemathesis configured in `contracts/schemathesis.toml`

---

## Related Files

- `pyproject.toml` - pytest configuration
- `coverage.xml` - Python coverage data
- `theo/services/web/vitest.config.ts` - Frontend test config
- `theo/services/web/package.json` - Frontend test scripts
- `contracts/schemathesis.toml` - API contract testing config
- `.github/workflows/` - CI/CD workflows

---

**Next Review:** After Phase 1 completion or in 2 weeks (whichever comes first)
