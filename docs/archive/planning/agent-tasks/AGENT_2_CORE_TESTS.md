# Agent Task 2: Core Infrastructure Tests

## Priority: CRITICAL
**Estimated Time:** 1-2 days  
**Owner:** Agent 2  
**Working Directory:** `tests/api/core/` (you will create this)

## Objective
Create comprehensive tests for core infrastructure (currently 0% coverage) to achieve 80%+ coverage.

## Current Status
```
Package: services.api.app.core
Coverage: 0.0% (0/7 files tested)
Priority: CRITICAL - Core system functionality
```

## Files You Own (Exclusive)
All files in: `theo/services/api/app/core/`
```
- database.py (547 bytes)
- runtime.py (437 bytes)
- secret_migration.py (475 bytes)
- settings.py (527 bytes)
- settings_store.py (659 bytes)
- version.py (415 bytes)
```

Your test directory: `tests/api/core/` (create this)

## Tasks

### 1. Study the Core Modules
Read each file in `theo/services/api/app/core/` to understand:
- Database connection management
- Settings loading and validation
- Runtime environment detection
- Secret management
- Version information

### 2. Create Test Structure
```
tests/api/core/
├── __init__.py
├── test_database.py
├── test_runtime.py
├── test_secret_migration.py
├── test_settings.py
├── test_settings_store.py
└── test_version.py
```

### 3. Write Comprehensive Tests

#### test_database.py
- Database session lifecycle
- Connection pooling
- Transaction management
- Error handling
- Cleanup

#### test_runtime.py
- Environment detection
- Configuration loading
- Runtime state management

#### test_secret_migration.py
- Secret migration logic
- Error handling
- Rollback scenarios

#### test_settings.py
- Settings loading from env
- Validation
- Default values
- Override behavior

#### test_settings_store.py
- Settings persistence
- Read/write operations
- Concurrent access

#### test_version.py
- Version string format
- Version comparison
- Git info (if available)

### 4. Follow Existing Patterns
Look at these files for patterns:
- `tests/conftest.py` - Shared fixtures
- `tests/api/conftest.py` - API fixtures
- `tests/db/test_sqlite_migrations.py` - Database testing patterns

## Test Template
```python
"""Tests for [module_name]."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from theo.infrastructure.api.app.core import [module]


class Test[Module]:
    """Test suite for [module]."""
    
    def test_happy_path(self):
        """Test basic functionality."""
        # Arrange
        
        # Act
        
        # Assert
        pass
    
    def test_error_handling(self):
        """Test error scenarios."""
        with pytest.raises(ExpectedException):
            # code that should fail
            pass
    
    @pytest.mark.parametrize("input,expected", [
        ("case1", "result1"),
        ("case2", "result2"),
    ])
    def test_multiple_scenarios(self, input, expected):
        """Test multiple cases."""
        assert function(input) == expected


def test_integration_scenario():
    """Test integration between modules."""
    # Test cross-module functionality
    pass
```

## Running Tests
```bash
# Test only your package
python -m pytest tests/api/core/ -v

# Test with coverage
python -m pytest tests/api/core/ --cov=theo.infrastructure.api.app.core --cov-report=term-missing

# Verify 80%+ coverage
python -m pytest tests/api/core/ --cov=theo.infrastructure.api.app.core --cov-fail-under=80
```

## Success Criteria
- [ ] All 6 test files created
- [ ] Each source file has corresponding tests
- [ ] Coverage ≥ 80% for `services.api.app.core`
- [ ] All tests passing
- [ ] No test conflicts with existing tests

## Key Testing Considerations

### Database Tests
- Use test fixtures from `tests/conftest.py`
- Clean up connections after tests
- Test both success and failure paths
- Mock external dependencies

### Settings Tests
- Mock environment variables
- Test validation logic
- Test default values
- Don't affect global state

### Runtime Tests
- Mock system calls if needed
- Test different environment modes
- Verify configuration merging

## No Conflicts With
- Agent 1: Working on frontend tests
- Agent 3: Working on MCP (`theo/services/api/app/mcp/`)
- Agent 4: Working on ingest (`theo/services/api/app/ingest/`)
- Agent 5: Working on retriever (`theo/services/api/app/retriever/`)
- Agent 6: Working on AI/RAG (`theo/services/api/app/ai/`)

## Report Format
```markdown
# Agent 2 Report: Core Infrastructure Tests

## Files Created
- tests/api/core/test_database.py ([X] tests)
- tests/api/core/test_runtime.py ([X] tests)
- tests/api/core/test_secret_migration.py ([X] tests)
- tests/api/core/test_settings.py ([X] tests)
- tests/api/core/test_settings_store.py ([X] tests)
- tests/api/core/test_version.py ([X] tests)

## Coverage Results
- Before: 0.0%
- After: [X]% ✅ (Target: 80%+)

## Test Breakdown
- Total tests: [X]
- Passing: [X]
- Edge cases covered: [list]
- Integration tests: [X]

## Challenges & Solutions
[Any issues encountered and how you solved them]

## Time Taken
[X] hours
```
