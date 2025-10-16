# Agent Coordination Guide

## 6 Parallel Agents - No Conflicts

### Agent Assignments

| Agent | Package | Directory | Coverage Goal |
|-------|---------|-----------|---------------|
| **Agent 1** | Frontend | `theo/services/web/tests/` | Fix failures |
| **Agent 2** | Core | `tests/api/core/` | 0% → 80% |
| **Agent 3** | MCP | `tests/mcp_tools/` | 0% → 80% |
| **Agent 4** | Ingest | `tests/ingest/` | 16% → 70% |
| **Agent 5** | Retriever | `tests/api/retriever/` | 13% → 70% |
| **Agent 6** | AI/RAG | `tests/api/ai/` | 23% → 70% |

## No Conflicts Because

Each agent works in:
- **Different source directories** (no file overlap)
- **Different test directories** (no test file conflicts)
- **Different packages** (no import conflicts)

## Coordination

### Starting All Agents
```bash
# Give each agent their specific prompt file
Agent 1: Read docs/agent-tasks/AGENT_1_FRONTEND_TESTS.md
Agent 2: Read docs/agent-tasks/AGENT_2_CORE_TESTS.md
Agent 3: Read docs/agent-tasks/AGENT_3_MCP_TESTS.md
Agent 4: Read docs/agent-tasks/AGENT_4_INGEST_TESTS.md
Agent 5: Read docs/agent-tasks/AGENT_5_RETRIEVER_TESTS.md
Agent 6: Read docs/agent-tasks/AGENT_6_AI_RAG_TESTS.md
```

### Checking Progress
```bash
# Each agent can run their tests independently
pytest tests/api/core/          # Agent 2
pytest tests/mcp_tools/         # Agent 3
pytest tests/ingest/            # Agent 4
pytest tests/api/retriever/     # Agent 5
pytest tests/api/ai/            # Agent 6
npm run test:vitest             # Agent 1 (in theo/services/web/)
```

### Final Integration
After all agents complete:
```bash
# Run full test suite
python -m pytest --cov=theo --cov=mcp_server --cov-report=term-missing

# Generate coverage report
python analyze_coverage.py
```

## Expected Timeline

### Week 1 Completion
- Agent 1: 2-4 hours
- Agent 2: 1-2 days
- Agent 3: 4-8 hours
- Agent 4: 3-5 days
- Agent 5: 2-3 days
- Agent 6: 4-6 days

**Parallel**: All complete within ~5 days (vs 15+ days sequential)

## Success Metrics

### Individual Agent Success
- Agent completes assigned tests
- Achieves coverage target
- All tests pass
- No conflicts with other agents

### Overall Success
- Overall coverage: 28.3% → 50%+
- Zero packages at 0% coverage
- All test suites passing
- No merge conflicts

## Communication Protocol

Each agent reports:
1. **Start**: "Agent X starting [package] tests"
2. **Progress**: Coverage % achieved
3. **Blockers**: Any issues encountered
4. **Complete**: Final coverage + test count

## Merge Order
1. Agent 1 (frontend) - Independent
2. Agent 2 (core) - Foundational
3. Agent 3 (mcp) - Independent
4. Agent 4 (ingest) - Independent
5. Agent 5 (retriever) - Independent
6. Agent 6 (ai/rag) - May depend on retriever

Or merge all simultaneously (no conflicts!)
