# Coverage Action Plan - Prioritized Tasks

## 🚨 Critical Priority - Week 1

### 1. Fix Frontend Test Failures
**Impact:** Blocks frontend coverage reporting  
**Effort:** Low (2-4 hours)

**Files:**
- `theo/services/web/tests/components/Toast.vitest.tsx` - Fix role selector assertions

**Actions:**
1. Review Toast component aria roles
2. Update test assertions to match actual implementation
3. Re-run: `npm run test:vitest`
4. Generate coverage baseline

---

### 2. Core Infrastructure Tests (0% → 80%)
**Impact:** High - Critical system components  
**Effort:** Medium (1-2 days)

**Zero-coverage files in `theo/services/api/app/core/`:**
```
✗ database.py         - Database connection/session management
✗ runtime.py          - Runtime configuration
✗ secret_migration.py - Secret management migrations
✗ settings.py         - Application settings
✗ settings_store.py   - Settings persistence
✗ version.py          - Version info
```

**Suggested test file:** `tests/api/core/test_core_infrastructure.py`

**Test scenarios:**
- Database connection lifecycle
- Settings loading and validation
- Secret migration logic
- Runtime environment detection
- Version information retrieval

---

### 3. MCP Server Tools Tests (0% → 80%)
**Impact:** High - MCP functionality exposed via ADR  
**Effort:** Low (4-8 hours)

**Zero-coverage files in `theo/services/api/app/mcp/`:**
```
✗ tools.py - MCP tool implementations (3,722 bytes)
```

**Suggested test file:** `tests/mcp_tools/test_api_mcp_integration.py`

**Test scenarios:**
- Tool registration
- Tool invocation
- Error handling
- Security boundaries
- Integration with MCP server

**Reference:** Existing `tests/mcp_tools/test_security_confinement.py` (21 tests)

---

## ⚠️ High Priority - Weeks 2-3

### 4. Ingest Pipeline (16.2% → 70%)
**Impact:** Very High - Core content processing  
**Effort:** High (3-5 days)

**Low-coverage files in `theo/services/api/app/ingest/` (13 files):**
- Document parsing
- Content extraction
- Metadata enrichment
- Error recovery

**Existing tests:** `tests/ingest/` (7 test files, 68+ tests)

**Gaps to fill:**
- Edge cases (malformed documents)
- Large file handling
- Concurrent ingestion
- Pipeline failures and recovery

---

### 5. Retriever/Search (12.8% → 70%)
**Impact:** Very High - Search functionality  
**Effort:** Medium (2-3 days)

**Low-coverage files in `theo/services/api/app/retriever/` (8 files):**
- Query processing
- Result ranking
- Semantic search
- Hybrid search

**Test scenarios:**
- Query parsing and validation
- Search result ranking
- Reranking algorithms
- Performance under load
- Edge cases (empty queries, special characters)

---

### 6. Case Builder (10.7% → 70%)
**Impact:** High - Research feature  
**Effort:** Low (1 day)

**Low-coverage files in `theo/services/api/app/case_builder/` (3 files):**
- Case construction
- Evidence gathering
- Citation management

**Fixtures available:** `fixtures/case_builder/` (3 files)

---

### 7. AI/RAG Systems (23.4% → 70%)
**Impact:** Very High - Core AI functionality  
**Effort:** High (4-6 days)

**Low-coverage in `theo/services/api/app/ai/` (9 files):**
- Prompt engineering
- Context management
- Response generation
- Guardrails

**Low-coverage in `theo/services/api/app/ai/rag/` (10 files):**
- RAG pipeline
- Context retrieval
- Answer generation
- Source attribution

**Existing tests:** 
- `tests/api/ai/test_reasoning_modules.py` (27 tests)
- `tests/api/test_ai_router.py` (20 tests)
- `tests/api/test_rag_guardrails_enhanced.py` (30 tests)

**Gaps:**
- Integration tests
- Error scenarios
- Performance tests
- Quality metrics

---

## 📊 Medium Priority - Weeks 4-6

### 8. API Routes (33.4% → 70%)
**Impact:** High - API surface  
**Effort:** Medium (2-3 days)

**Low-coverage in `theo/services/api/app/routes/` (15 files):**
- Request validation
- Response formatting
- Error handling
- Authentication/authorization

**Approach:**
- API contract testing (Schemathesis configured)
- Integration tests
- Error response validation

---

### 9. Workflow Orchestration (24.8% → 70%)
**Impact:** High - AI workflows  
**Effort:** Medium (2-3 days)

**Low-coverage in `theo/services/api/app/routes/ai/workflows/` (9 files):**
- Workflow execution
- State management
- Error recovery
- Async operations

**Existing tests:**
- `tests/api/test_workflows_guardrails.py` (4 tests)
- `tests/api/test_workflow_spans.py` (4 tests)

---

### 10. Analytics & Monitoring (17.9% → 70%)
**Impact:** Medium - Observability  
**Effort:** Low (1 day)

**Low-coverage in `theo/services/api/app/analytics/` (4 files):**
- Event tracking
- Metrics collection
- Dashboard data

---

### 11. Export Functionality (15.5% → 70%)
**Impact:** Medium - User-facing feature  
**Effort:** Low (1 day)

**Low-coverage in `theo/services/api/app/export/` (3 files):**
- Document export
- Citation formatting
- Format conversion

**Existing tests:**
- `tests/export/test_citation_formatters.py` (5 tests)
- `tests/export/test_document_export_formatters.py` (4 tests)

---

## 📈 Metrics & Tracking

### Weekly Coverage Goals

| Week | Target | Focus Area |
|------|--------|------------|
| 1 | 35% | Frontend fixes + Core infrastructure |
| 2 | 40% | Ingest + Retriever |
| 3 | 45% | Case Builder + AI/RAG basics |
| 4 | 50% | AI/RAG integration + API routes |
| 5 | 60% | Workflow + Export |
| 6 | 70% | Analytics + Edge cases |
| 8 | 80% | Final push + quality |

### Success Metrics

**Phase 1 (Week 1) - Foundation:**
- ✅ 0 failing frontend tests
- ✅ 0 packages at 0% coverage
- ✅ Coverage reporting automated

**Phase 2 (Weeks 2-3) - Critical Paths:**
- ✅ Ingest ≥ 70%
- ✅ Retriever ≥ 70%
- ✅ AI/RAG ≥ 60%
- ✅ Overall ≥ 45%

**Phase 3 (Weeks 4-6) - Comprehensive:**
- ✅ All packages ≥ 50%
- ✅ API routes ≥ 70%
- ✅ Overall ≥ 70%

**Phase 4 (Weeks 7-8) - Quality:**
- ✅ Overall ≥ 80%
- ✅ CI gates enabled
- ✅ Documentation complete

---

## Test Templates

### Basic Unit Test Template
```python
"""Tests for [module_name]."""
import pytest
from unittest.mock import Mock, patch

from theo.services.api.app.[module] import [function_or_class]

class Test[FunctionOrClass]:
    """Test suite for [FunctionOrClass]."""
    
    def test_happy_path(self):
        """Test basic functionality works as expected."""
        # Arrange
        input_data = ...
        expected_output = ...
        
        # Act
        result = [function_or_class](input_data)
        
        # Assert
        assert result == expected_output
    
    def test_edge_case_empty_input(self):
        """Test handling of empty input."""
        pass
    
    def test_error_handling(self):
        """Test error scenarios raise appropriate exceptions."""
        with pytest.raises(ValueError):
            [function_or_class](invalid_input)
    
    @pytest.mark.parametrize("input,expected", [
        ("case1", "result1"),
        ("case2", "result2"),
    ])
    def test_multiple_scenarios(self, input, expected):
        """Test multiple input scenarios."""
        assert [function_or_class](input) == expected
```

### Integration Test Template
```python
"""Integration tests for [feature]."""
import pytest
from fastapi.testclient import TestClient

from theo.services.api.app.main import app

@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)

def test_feature_integration(client, db_session):
    """Test feature end-to-end integration."""
    # Setup test data
    
    # Execute request
    response = client.post("/api/endpoint", json={...})
    
    # Verify response
    assert response.status_code == 200
    assert response.json()["key"] == "value"
    
    # Verify side effects (database, etc.)
```

---

## Automation Scripts

### Generate Coverage Report
```bash
#!/bin/bash
# scripts/coverage.sh

echo "Running Python backend tests with coverage..."
python -m pytest --cov=theo --cov=mcp_server \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=xml \
  --cov-fail-under=0

echo "\nGenerating coverage analysis..."
python analyze_coverage.py

echo "\nRunning frontend tests with coverage..."
cd theo/services/web
npm run test:vitest

echo "\nCoverage reports generated:"
echo "- Backend HTML: htmlcov/index.html"
echo "- Backend XML: coverage.xml"
echo "- Frontend: theo/services/web/coverage/"
```

### Daily Coverage Check
```bash
#!/bin/bash
# scripts/check_coverage_daily.sh

CURRENT_COVERAGE=$(python -c "import xml.etree.ElementTree as ET; print(float(ET.parse('coverage.xml').getroot().get('line-rate')) * 100)")
THRESHOLD=28.3  # Update weekly

if (( $(echo "$CURRENT_COVERAGE < $THRESHOLD" | bc -l) )); then
  echo "❌ Coverage decreased: $CURRENT_COVERAGE% < $THRESHOLD%"
  exit 1
else
  echo "✅ Coverage: $CURRENT_COVERAGE%"
  exit 0
fi
```

---

## Resources

### Documentation
- [pytest documentation](https://docs.pytest.org/)
- [Vitest documentation](https://vitest.dev/)
- [Testing best practices](https://testdriven.io/blog/testing-best-practices/)

### Internal
- `tests/conftest.py` - Shared fixtures
- `tests/api/conftest.py` - API test fixtures
- Existing test files for patterns and examples

### Tools
- pytest-cov: Coverage measurement
- pytest-xdist: Parallel test execution
- Schemathesis: API contract testing
- Playwright: E2E testing

---

**Next Steps:**
1. Review this plan in team meeting
2. Assign Week 1 tasks
3. Set up daily coverage checks
4. Schedule weekly progress reviews
