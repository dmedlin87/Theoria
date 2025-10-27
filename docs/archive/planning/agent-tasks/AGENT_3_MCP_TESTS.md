# Agent Task 3: MCP Integration Tests

## Priority: CRITICAL
**Estimated Time:** 4-8 hours  
**Owner:** Agent 3  
**Working Directory:** `tests/mcp_tools/` (existing)

## Objective
Create comprehensive tests for MCP API integration (currently 0% coverage) to achieve 80%+ coverage.

## Current Status
```
Package: services.api.app.mcp
Coverage: 0.0% (0/2 files tested)
Priority: CRITICAL - MCP functionality exposed via ADR
```

## Files You Own (Exclusive)
All files in: `theo/services/api/app/mcp/`
```
- __init__.py (163 bytes)
- tools.py (3,722 bytes) - MAIN FILE TO TEST
```

Your test file: `tests/mcp_tools/test_api_mcp_integration.py` (create this)

## Context: What is MCP?
Read this ADR first: `docs/adr/0001-expose-theoengine-via-mcp.md`

MCP (Model Context Protocol) exposes TheoEngine capabilities as tools. The `tools.py` file implements MCP tool wrappers around the API.

## Related Existing Tests
```
tests/mcp_tools/
├── test_security_confinement.py (21 tests) ✅
├── test_read_tools.py (5 tests) ✅
└── test_write_tools.py (8 tests) ✅
```

These test the MCP SERVER side. You need to test the API INTEGRATION side.

## Tasks

### 1. Study MCP API Integration
Read thoroughly:
- `theo/services/api/app/mcp/tools.py` - The code you're testing
- `mcp_server/tools/*.py` - Related MCP server tools
- `docs/adr/0001-expose-theoengine-via-mcp.md` - Architecture decision

### 2. Create Test File
Create: `tests/mcp_tools/test_api_mcp_integration.py`

### 3. Test Coverage Areas

#### Tool Registration
- Tools are properly registered
- Tool metadata is correct
- Tool discovery works

#### Tool Invocation
- Each tool can be called
- Arguments are validated
- Return values are correct format

#### API Integration
- Tools correctly call underlying API functions
- Error handling works
- Authentication/authorization is enforced

#### Security & Confinement
- Tools respect security boundaries
- No path traversal vulnerabilities
- Input sanitization works

#### Error Handling
- Invalid arguments rejected
- API errors propagated correctly
- Timeout handling
- Connection errors handled

## Test Template
```python
"""Integration tests for MCP API tools."""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from theo.infrastructure.api.app.mcp import tools


class TestMCPToolRegistration:
    """Test MCP tool registration and discovery."""
    
    def test_all_tools_registered(self):
        """Verify all expected tools are registered."""
        expected_tools = [
            # List expected tool names
        ]
        # Assert all tools present
        pass
    
    def test_tool_metadata_valid(self):
        """Verify tool metadata is complete and valid."""
        pass


class TestMCPToolInvocation:
    """Test MCP tool invocation."""
    
    @pytest.mark.asyncio
    async def test_tool_invocation_success(self):
        """Test successful tool invocation."""
        pass
    
    @pytest.mark.asyncio
    async def test_tool_invocation_invalid_args(self):
        """Test tool invocation with invalid arguments."""
        with pytest.raises(ValueError):
            # Call with invalid args
            pass


class TestMCPAPIIntegration:
    """Test integration between MCP tools and API."""
    
    @pytest.mark.asyncio
    async def test_read_tool_calls_api(self, mock_api):
        """Test read tools call correct API endpoints."""
        pass
    
    @pytest.mark.asyncio
    async def test_write_tool_calls_api(self, mock_api):
        """Test write tools call correct API endpoints."""
        pass


class TestMCPSecurity:
    """Test MCP security boundaries."""
    
    def test_confinement_boundaries(self):
        """Test tools respect confinement boundaries."""
        # Reference: tests/mcp_tools/test_security_confinement.py
        pass
    
    def test_input_sanitization(self):
        """Test input sanitization prevents injection."""
        pass


class TestMCPErrorHandling:
    """Test MCP error handling."""
    
    @pytest.mark.asyncio
    async def test_api_error_propagation(self):
        """Test API errors are properly propagated."""
        pass
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout scenarios."""
        pass
```

## Fixtures Needed
```python
@pytest.fixture
def mcp_tools_instance():
    """Provide MCP tools instance for testing."""
    # Setup
    yield tools_instance
    # Teardown

@pytest.fixture
def mock_api():
    """Mock API responses."""
    with patch('theo.infrastructure.api.app.mcp.tools.some_api_call') as mock:
        yield mock
```

## Running Tests
```bash
# Test only your file
python -m pytest tests/mcp_tools/test_api_mcp_integration.py -v

# Test with coverage for MCP package
python -m pytest tests/mcp_tools/test_api_mcp_integration.py \
  --cov=theo.infrastructure.api.app.mcp \
  --cov-report=term-missing

# Verify 80%+ coverage
python -m pytest tests/mcp_tools/test_api_mcp_integration.py \
  --cov=theo.infrastructure.api.app.mcp \
  --cov-fail-under=80

# Run all MCP tests together
python -m pytest tests/mcp_tools/ -v
```

## Success Criteria
- [ ] `test_api_mcp_integration.py` created
- [ ] Coverage ≥ 80% for `services.api.app.mcp`
- [ ] All tests passing
- [ ] No conflicts with existing MCP tests
- [ ] Security tests included

## Key Testing Considerations

### Integration Testing
- Mock external API calls
- Test both success and failure paths
- Verify correct API methods called
- Check arguments passed correctly

### Security Testing
- Path traversal prevention
- Input validation
- Authorization checks
- Rate limiting (if applicable)

### Async Testing
- Use `pytest.mark.asyncio`
- Properly await async calls
- Test concurrent operations
- Handle timeouts

## Reference Existing Tests
Study these for patterns:
- `tests/mcp_tools/test_security_confinement.py` - Security patterns
- `tests/mcp_tools/test_read_tools.py` - Read operation patterns
- `tests/mcp_tools/test_write_tools.py` - Write operation patterns

## No Conflicts With
- Agent 1: Working on frontend tests
- Agent 2: Working on core (`tests/api/core/`)
- Agent 4: Working on ingest (`theo/services/api/app/ingest/`)
- Agent 5: Working on retriever (`theo/services/api/app/retriever/`)
- Agent 6: Working on AI/RAG (`theo/services/api/app/ai/`)

## Report Format
```markdown
# Agent 3 Report: MCP Integration Tests

## Files Created
- tests/mcp_tools/test_api_mcp_integration.py

## Test Breakdown
- Tool registration tests: [X]
- Tool invocation tests: [X]
- API integration tests: [X]
- Security tests: [X]
- Error handling tests: [X]
- Total tests: [X]

## Coverage Results
- Before: 0.0%
- After: [X]% ✅ (Target: 80%+)
- Lines covered: [X]/[Y]

## Key Test Scenarios
1. [Scenario 1]
2. [Scenario 2]
3. [Scenario 3]

## Integration Points Tested
- [API endpoint 1]
- [API endpoint 2]
- [Security boundary 1]

## Time Taken
[X] hours
```
