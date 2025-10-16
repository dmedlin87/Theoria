# Parallel Agent Task Distribution

## Quick Start - Copy These Prompts

### 🤖 Agent 1: Frontend Test Fixes
```
Read the file: docs/agent-tasks/AGENT_1_FRONTEND_TESTS.md

Your mission: Fix 2 failing frontend test suites in theo/services/web/tests/components/Toast.vitest.tsx to enable coverage reporting.

Working directory: theo/services/web/
Target: All 42 tests passing
Time: 2-4 hours

You own: All files in theo/services/web/tests/components/
No conflicts with other agents.
```

### 🤖 Agent 2: Core Infrastructure Tests
```
Read the file: docs/agent-tasks/AGENT_2_CORE_TESTS.md

Your mission: Create comprehensive tests for core infrastructure (database, settings, runtime) currently at 0% coverage.

Working directory: tests/api/core/ (you will create this)
Target: 80%+ coverage for theo/services/api/app/core/
Time: 1-2 days

You own: theo/services/api/app/core/ (7 files)
No conflicts with other agents.
```

### 🤖 Agent 3: MCP Integration Tests
```
Read the file: docs/agent-tasks/AGENT_3_MCP_TESTS.md

Your mission: Create comprehensive tests for MCP API integration currently at 0% coverage.

Working directory: tests/mcp_tools/
Target: 80%+ coverage for theo/services/api/app/mcp/
Time: 4-8 hours

You own: theo/services/api/app/mcp/ (2 files)
No conflicts with other agents.
```

### 🤖 Agent 4: Ingest Pipeline Tests
```
Read the file: docs/agent-tasks/AGENT_4_INGEST_TESTS.md

Your mission: Boost ingest pipeline coverage from 16.2% to 70%+ by adding edge case, error recovery, and integration tests.

Working directory: tests/ingest/ (expand existing)
Target: 70%+ coverage for theo/services/api/app/ingest/
Time: 3-5 days

You own: theo/services/api/app/ingest/ (13 files)
No conflicts with other agents.
```

### 🤖 Agent 5: Retriever/Search Tests
```
Read the file: docs/agent-tasks/AGENT_5_RETRIEVER_TESTS.md

Your mission: Boost retriever/search coverage from 12.8% to 70%+ with comprehensive search functionality tests.

Working directory: tests/api/retriever/ (you will create this)
Target: 70%+ coverage for theo/services/api/app/retriever/
Time: 2-3 days

You own: theo/services/api/app/retriever/ (8 files)
No conflicts with other agents.
```

### 🤖 Agent 6: AI/RAG Tests
```
Read the file: docs/agent-tasks/AGENT_6_AI_RAG_TESTS.md

Your mission: Boost AI/RAG coverage from 23-25% to 70%+ with RAG pipeline, context retrieval, and answer generation tests.

Working directory: tests/api/ai/ (expand existing)
Target: 70%+ coverage for theo/services/api/app/ai/ and ai/rag/
Time: 4-6 days

You own: theo/services/api/app/ai/ (9 files) and ai/rag/ (10 files)
No conflicts with other agents.
```

---

## Why No Conflicts?

Each agent works in:
- ✅ **Different source code directories**
- ✅ **Different test file locations**
- ✅ **Different Python packages**
- ✅ **Different test files**

### Directory Isolation

```
Agent 1: theo/services/web/tests/components/
Agent 2: tests/api/core/                      (new directory)
Agent 3: tests/mcp_tools/                     (existing, new file)
Agent 4: tests/ingest/                        (existing, expand)
Agent 5: tests/api/retriever/                 (new directory)
Agent 6: tests/api/ai/                        (existing, expand)
```

No overlapping directories = no merge conflicts!

---

## Expected Results

### Individual Coverage Improvements
- Agent 1: Frontend → 100% passing tests
- Agent 2: Core 0% → 80%
- Agent 3: MCP 0% → 80%
- Agent 4: Ingest 16% → 70%
- Agent 5: Retriever 13% → 70%
- Agent 6: AI/RAG 23% → 70%

### Overall Coverage
- **Before:** 28.3%
- **After:** 50-60%+ (target: 80% in 8 weeks)

### Timeline
- **Sequential:** 15+ days
- **Parallel:** 5-6 days (agents work simultaneously)

---

## Monitoring Progress

### Check Individual Agent
```bash
# Agent 1
cd theo/services/web && npm run test:vitest

# Agent 2
pytest tests/api/core/ --cov=theo.services.api.app.core --cov-report=term-missing

# Agent 3
pytest tests/mcp_tools/test_api_mcp_integration.py --cov=theo.services.api.app.mcp

# Agent 4
pytest tests/ingest/ --cov=theo.services.api.app.ingest --cov-report=term-missing

# Agent 5
pytest tests/api/retriever/ --cov=theo.services.api.app.retriever --cov-report=term-missing

# Agent 6
pytest tests/api/ai/ --cov=theo.services.api.app.ai --cov-report=term-missing
```

### Check Overall Progress
```bash
# Full test suite
python -m pytest --cov=theo --cov=mcp_server --cov-report=term-missing

# Generate dashboard
python analyze_coverage.py
```

---

## Agent Deliverables

Each agent should provide:
1. ✅ Test files created/modified
2. ✅ Coverage percentage achieved
3. ✅ Number of tests added
4. ✅ All tests passing
5. ✅ Brief summary of changes

---

## Files Structure

```
docs/agent-tasks/
├── README.md                    ← You are here
├── AGENT_COORDINATOR.md         ← Coordination guide
├── AGENT_1_FRONTEND_TESTS.md    ← Frontend test fixes
├── AGENT_2_CORE_TESTS.md        ← Core infrastructure tests
├── AGENT_3_MCP_TESTS.md         ← MCP integration tests
├── AGENT_4_INGEST_TESTS.md      ← Ingest pipeline tests
├── AGENT_5_RETRIEVER_TESTS.md   ← Retriever/search tests
└── AGENT_6_AI_RAG_TESTS.md      ← AI/RAG tests
```

---

## Success Criteria

✅ All 6 agents complete their tasks
✅ No merge conflicts between agents
✅ Overall coverage increases by ~25+ percentage points
✅ All test suites passing
✅ Zero packages at 0% coverage
