# Agent Task 4: Ingest Pipeline Tests

## Priority: HIGH
**Estimated Time:** 3-5 days  
**Owner:** Agent 4  
**Working Directory:** `tests/ingest/` (existing)

## Objective
Boost ingest pipeline coverage from 16.2% to 70%+ by adding edge case and integration tests.

## Current Status
```
Package: services.api.app.ingest
Coverage: 16.2% (13 files)
Priority: CRITICAL - Core content processing
Existing tests: 68+ tests in 7 files
```

## Files You Own (Exclusive)
All files in: `theo/services/api/app/ingest/` (13 files)

Your test directory: `tests/ingest/` (existing, expand this)

## Existing Tests (Study These First)
```
tests/ingest/
├── test_pipeline.py (18 tests) ✅
├── test_cli_ingest_folder.py (13 tests) ✅
├── test_osis_utils.py (10 tests) ✅
├── test_parsers.py (4 tests) ✅
└── [3 more files]
```

## Current Coverage Gaps
You need to add tests for:
1. **Edge cases** - Malformed documents, large files, encoding issues
2. **Error recovery** - Pipeline failures, rollback, retry logic
3. **Concurrent ingestion** - Multiple uploads, race conditions
4. **Performance** - Large batches, memory management
5. **Integration** - End-to-end pipeline flows

## Tasks

### 1. Analyze Coverage Gaps
```bash
# See exactly what's not covered
python -m pytest tests/ingest/ \
  --cov=theo.infrastructure.api.app.ingest \
  --cov-report=html

# Open: htmlcov/index.html
# Review: Which lines/functions are red (not covered)?
```

### 2. Identify Untested Scenarios
Read the source files in `theo/services/api/app/ingest/` and identify:
- Error handling code paths
- Conditional branches
- Exception handlers
- Edge cases
- Validation logic

### 3. Create New Test Files (as needed)
Suggested new test files:
```
tests/ingest/
├── test_ingest_edge_cases.py (NEW)
├── test_ingest_error_recovery.py (NEW)
├── test_ingest_concurrent.py (NEW)
├── test_ingest_performance.py (NEW)
├── test_ingest_integration.py (NEW)
```

### 4. Expand Existing Tests
Add tests to existing files for missed branches/lines.

## Test Scenarios to Add

### Edge Cases (`test_ingest_edge_cases.py`)
```python
"""Edge case tests for ingest pipeline."""
import pytest

class TestIngestEdgeCases:
    """Test edge cases in document ingestion."""
    
    def test_empty_document(self):
        """Test ingesting empty document."""
        pass
    
    def test_malformed_document(self):
        """Test ingesting malformed/corrupted document."""
        pass
    
    def test_very_large_document(self):
        """Test ingesting document >100MB."""
        pass
    
    def test_special_characters_in_content(self):
        """Test documents with special/unicode characters."""
        pass
    
    def test_encoding_issues(self):
        """Test various text encodings (UTF-8, Latin-1, etc)."""
        pass
    
    def test_missing_metadata(self):
        """Test documents with incomplete metadata."""
        pass
    
    @pytest.mark.parametrize("extension", [".pdf", ".docx", ".html", ".md", ".txt"])
    def test_various_file_types(self, extension):
        """Test ingesting various file types."""
        pass
```

### Error Recovery (`test_ingest_error_recovery.py`)
```python
"""Error recovery tests for ingest pipeline."""
import pytest
from unittest.mock import patch

class TestIngestErrorRecovery:
    """Test error recovery in ingest pipeline."""
    
    def test_pipeline_failure_rollback(self, db_session):
        """Test pipeline rolls back on failure."""
        pass
    
    def test_partial_ingestion_recovery(self):
        """Test recovering from partial ingestion."""
        pass
    
    @patch('theo.infrastructure.api.app.ingest.stage.StageX.process')
    def test_stage_failure_handling(self, mock_process):
        """Test handling of stage failures."""
        mock_process.side_effect = Exception("Stage failed")
        # Assert proper error handling
        pass
    
    def test_retry_logic(self):
        """Test retry logic on transient failures."""
        pass
    
    def test_dead_letter_queue(self):
        """Test failed documents go to DLQ."""
        pass
```

### Concurrent Ingestion (`test_ingest_concurrent.py`)
```python
"""Concurrent ingestion tests."""
import pytest
import asyncio
from concurrent.futures import ThreadPoolExecutor

class TestConcurrentIngestion:
    """Test concurrent document ingestion."""
    
    @pytest.mark.asyncio
    async def test_multiple_simultaneous_ingests(self):
        """Test multiple documents ingested simultaneously."""
        pass
    
    def test_race_condition_prevention(self, db_session):
        """Test no race conditions in concurrent uploads."""
        pass
    
    def test_resource_locking(self):
        """Test proper resource locking during ingestion."""
        pass
    
    def test_concurrent_same_document(self):
        """Test handling same document uploaded concurrently."""
        pass
```

### Performance (`test_ingest_performance.py`)
```python
"""Performance tests for ingest pipeline."""
import pytest
import time

class TestIngestPerformance:
    """Test ingest pipeline performance."""
    
    @pytest.mark.slow
    def test_large_batch_ingestion(self):
        """Test ingesting 100+ documents in batch."""
        pass
    
    @pytest.mark.slow
    def test_memory_usage(self):
        """Test memory doesn't grow unbounded."""
        pass
    
    def test_processing_time_bounds(self):
        """Test processing time within acceptable limits."""
        start = time.time()
        # Ingest document
        elapsed = time.time() - start
        assert elapsed < 10.0, "Processing too slow"
```

### Integration (`test_ingest_integration.py`)
```python
"""End-to-end integration tests."""
import pytest

class TestIngestIntegration:
    """Test complete ingest pipeline integration."""
    
    def test_upload_to_searchable(self, client, db_session):
        """Test document from upload to searchable."""
        # 1. Upload document
        # 2. Verify ingested
        # 3. Verify indexed
        # 4. Verify searchable
        pass
    
    def test_ingest_with_enrichment(self):
        """Test ingestion + metadata enrichment."""
        pass
    
    def test_ingest_with_analytics(self):
        """Test ingestion triggers analytics."""
        pass
```

## Available Fixtures
Check `tests/ingest/` and `tests/conftest.py` for fixtures like:
- Sample documents (fixtures/markdown/, fixtures/html/)
- Database sessions
- Mock file uploads
- Test data builders

## Running Tests
```bash
# Run all ingest tests
python -m pytest tests/ingest/ -v

# Run with coverage
python -m pytest tests/ingest/ \
  --cov=theo.infrastructure.api.app.ingest \
  --cov-report=term-missing \
  --cov-report=html

# Run specific test file
python -m pytest tests/ingest/test_ingest_edge_cases.py -v

# Run slow tests (performance)
python -m pytest tests/ingest/ -v -m slow
```

## Success Criteria
- [ ] Coverage increased from 16.2% to ≥70%
- [ ] Edge cases comprehensively tested
- [ ] Error recovery scenarios covered
- [ ] All new tests passing
- [ ] No regressions in existing tests

## Key Testing Considerations

### Use Existing Fixtures
```python
# From fixtures/
- fixtures/markdown/README.md
- fixtures/html/sample_page.html
- fixtures/case_builder/*.json
```

### Database Testing
- Use `db_session` fixture
- Clean up after tests
- Test transactions and rollbacks

### File Upload Testing
- Create temporary files
- Test multipart/form-data
- Clean up test files

### Performance Testing
- Mark with `@pytest.mark.slow`
- Set reasonable thresholds
- Don't block CI with long tests

## No Conflicts With
- Agent 1: Frontend tests
- Agent 2: Core tests (`tests/api/core/`)
- Agent 3: MCP tests (`tests/mcp_tools/`)
- Agent 5: Retriever tests (`tests/api/retriever/`)
- Agent 6: AI tests (`tests/api/ai/`)

## Report Format
```markdown
# Agent 4 Report: Ingest Pipeline Tests

## Coverage Improvement
- Before: 16.2%
- After: [X]% ✅ (Target: 70%+)
- New lines covered: [X]

## New Test Files
- test_ingest_edge_cases.py ([X] tests)
- test_ingest_error_recovery.py ([X] tests)
- test_ingest_concurrent.py ([X] tests)
- test_ingest_performance.py ([X] tests)
- test_ingest_integration.py ([X] tests)

## Test Breakdown
- Total new tests: [X]
- Edge cases: [X]
- Error recovery: [X]
- Concurrent: [X]
- Performance: [X]
- Integration: [X]

## Key Scenarios Covered
1. [Scenario 1]
2. [Scenario 2]
3. [Scenario 3]

## Challenges & Solutions
[Issues encountered and resolutions]

## Time Taken
[X] hours/days
```
