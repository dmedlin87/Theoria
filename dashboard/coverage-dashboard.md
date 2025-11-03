# 📊 Test Coverage Dashboard

> Last Updated: October 15, 2025 @ 4:45 PM UTC-05:00

## 🎯 Overall Status

<table>
<tr>
<td width="50%">

### Backend (Python)
```
Coverage: 28.3%
████████░░░░░░░░░░░░░░░░

Target:   80.0%
████████████████████████

Gap: -51.7%
```

**Lines:** 5,477 / 19,334  
**Files:** 109 test files  
**Tests:** 522 functions

</td>
<td width="50%">

### Frontend (TypeScript)
```
Status: ⚠️ 2 Failing Suites

Tests: 38 / 42 passing
███████████████████████░

Coverage: Not Generated
(Blocked by test failures)
```

**Files:** 47+ test files  
**E2E:** 7 Playwright specs  
**Tests:** 42 total

</td>
</tr>
</table>

---

## 📈 Coverage by Package (Top 20)

| Package | Coverage | Trend | Priority |
|---------|----------|-------|----------|
| 🔴 `services.api.app.core` | 0.0% | ▬ | 🚨 CRITICAL |
| 🔴 `services.api.app.retriever.tests` | 0.0% | ▬ | ⚠️ LOW |
| 🔴 `services.api.tests` | 0.0% | ▬ | ⚠️ LOW |
| 🔴 `services.api.tests.workers` | 0.0% | ▬ | ⚠️ LOW |
| 🔴 `services.api.app.case_builder` | 10.7% | ▬ | 🚨 HIGH |
| 🔴 `services.api.app.transcripts` | 11.8% | ▬ | ⚠️ MEDIUM |
| 🔴 `services.api.app.retriever` | 12.8% | ▬ | 🚨 CRITICAL |
| 🔴 `services.geo` | 14.1% | ▬ | ⚠️ MEDIUM |
| 🔴 `services.api.app.notebooks` | 14.6% | ▬ | ⚠️ MEDIUM |
| 🔴 `services.api.app.export` | 15.5% | ▬ | ⚠️ MEDIUM |
| 🔴 `services.api.app.ingest` | 16.2% | ▬ | 🚨 CRITICAL |
| 🔴 `services.api.app.enrich` | 16.4% | ▬ | ⚠️ MEDIUM |
| 🔴 `services.api.app.analytics` | 17.9% | ▬ | ⚠️ MEDIUM |
| 🔴 `services.api.app.workers` | 18.4% | ▬ | ⚠️ MEDIUM |
| 🟡 `services.api.app.ai.rag` | 23.4% | ▬ | 🚨 CRITICAL |
| 🟡 `services.api.app.creators` | 23.5% | ▬ | ⚠️ MEDIUM |
| 🟡 `services.cli` | 24.1% | ▬ | ⚠️ LOW |
| 🟡 `services.api.app.routes.ai.workflows` | 24.8% | ▬ | 🚨 HIGH |
| 🟡 `services.api.app.ai` | 25.5% | ▬ | 🚨 CRITICAL |

---

## 🎯 Week 1 Goals (Oct 15-22)

### Primary Objectives

<table>
<tr>
<th>Task</th>
<th>Current</th>
<th>Target</th>
<th>Status</th>
</tr>
<tr>
<td>Fix Frontend Tests</td>
<td>2 failing</td>
<td>0 failing</td>
<td>🔴 Not Started</td>
</tr>
<tr>
<td>Core Infrastructure</td>
<td>0%</td>
<td>80%</td>
<td>🔴 Not Started</td>
</tr>
<tr>
<td>Overall Coverage</td>
<td>28.3%</td>
<td>35%</td>
<td>🔴 Not Started</td>
</tr>
</table>

### Success Criteria
- ✅ All frontend tests passing
- ✅ Zero packages at 0% coverage
- ✅ Coverage scripts automated
- ✅ Daily coverage tracking enabled

---

## 📊 Coverage Heatmap

```
Package Categories by Coverage Level:

100%+ ████ (4)  platform, services, services.api, services.api.app.research.data
80-99% ███  (7)  models, adapters, domain, application
60-79% ██   (0)  (none)
40-59% ██   (6)  facades, routes.ai, services, db, app, ingest.stages
20-39% █    (10) workers, rag, creators, cli, workflows, ai, intent, ranking, debug, research
10-19% █    (9)  case_builder, transcripts, retriever, geo, notebooks, export, ingest, enrich, analytics
0-9%   █    (4)  core, retriever.tests, api.tests (2x)

Legend: █ = 5 packages
```

---

## 🚨 Critical Gaps

### Zero Coverage (5 packages, 36 files)
These packages have **NO TESTS** and represent **critical risk areas**:

1. **`core/`** (7 files) - Database, settings, runtime
2. **`retriever.tests/`** (2 files) - Old test files?
3. **`api.tests/`** (23 files) - Old test files?
4. **`api.tests.workers/`** (2 files) - Old test files?

### Under 20% Coverage (9 packages, 41 files)
Critical business logic with minimal testing:

- **Ingest Pipeline** (13 files) - Document processing
- **Retriever** (8 files) - Search functionality
- **Case Builder** (3 files) - Research features
- **Export** (3 files) - Document export
- **Analytics** (4 files) - Monitoring
- **Transcripts** (2 files) - Transcript handling
- **Notebooks** (1 file) - Notebook features
- **Enrichment** (2 files) - Metadata enrichment
- **Geo** (2 files) - Geographic data

---

## 📋 Test Inventory

### Python Tests
```
Total:   109 files
Tests:   522 functions

By Category:
- API:          ~300 tests (61 files)
- Ingest:        68 tests (7 files)
- AI/RAG:        77 tests (4 files)
- Architecture:   7 tests (1 file)
- Export:        17 tests (3 files)
- Database:      ~20 tests (3 files)
- Research:      ~15 tests (6 files)
- Other:         ~20 tests
```

### Frontend Tests
```
Total:   47+ files
Tests:   42 (38 passing, 4 failing)

By Category:
- Component:    ~15 tests
- Feature:      ~20 tests
- E2E:           7 specs
- Integration:   ~10 tests
```

---

## 🔧 Tools & Infrastructure

### Coverage Tools
- ✅ pytest-cov (Python)
- ✅ Vitest + coverage-v8 (Frontend)
- ✅ Playwright (E2E)
- ✅ Schemathesis (API contracts)

### CI/CD Integration
- ⚠️ Coverage disabled by default
- ❌ No coverage gates
- ❌ No coverage trending
- ✅ Test execution automated

### Reporting
- ✅ XML reports generated
- ✅ HTML reports available
- ✅ Terminal output
- ❌ Dashboard not integrated

---

## 📚 Quick Reference

### Run Tests
```bash
# Backend with coverage
python -m pytest --cov=theo \
  --cov-report=term-missing --cov-report=html

# Frontend (fix tests first!)
cd theo/services/web && npm run test:vitest

# E2E
cd theo/services/web && npm run test:e2e

# Coverage analysis
python analyze_coverage.py
```

### View Reports
```bash
# Backend HTML report
start htmlcov/index.html

# Frontend (once generated)
start theo/services/web/coverage/index.html

# E2E results
start theo/services/web/playwright-report/index.html
```

---

## 📅 Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Fix frontend test failures
- [ ] Add core infrastructure tests
- [ ] Setup automated coverage tracking
- **Target:** 35% overall coverage

### Phase 2: Critical Paths (Weeks 3-6)
- [ ] Ingest pipeline (16% → 70%)
- [ ] Retriever/search (13% → 70%)
- [ ] AI/RAG workflows (23% → 60%)
- [ ] Case builder (11% → 70%)
- **Target:** 50% overall coverage

### Phase 3: Comprehensive (Weeks 7-8)
- [ ] API routes (33% → 70%)
- [ ] Workflow orchestration (25% → 70%)
- [ ] Export functionality (16% → 70%)
- [ ] Analytics (18% → 70%)
- **Target:** 80% overall coverage

### Phase 4: Quality (Ongoing)
- [ ] Enable CI coverage gates
- [ ] Add branch coverage
- [ ] Performance benchmarks
- [ ] Mutation testing
- **Target:** Maintain 80%+

---

## 📖 Documentation

- **`COVERAGE_SUMMARY.md`** - Quick overview (this file)
- **`COVERAGE_REVIEW.md`** - Detailed analysis
- **`COVERAGE_ACTION_PLAN.md`** - Week-by-week tasks
- **`analyze_coverage.py`** - Coverage analysis script

---

## 👥 Team Ownership

| Area | Owner | Status |
|------|-------|--------|
| Backend Tests | TBD | 🔴 Needs Owner |
| Frontend Tests | TBD | 🔴 Needs Owner |
| E2E Tests | TBD | 🔴 Needs Owner |
| CI/CD | TBD | 🔴 Needs Owner |

---

**Next Review:** Monday, October 22, 2025 @ 9:00 AM  
**Dashboard Updated:** Automatically on test run  
**Questions?** See `COVERAGE_REVIEW.md` or contact team lead
