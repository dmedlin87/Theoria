# Agent Task 6: AI/RAG Tests

## Priority: HIGH | Time: 4-6 days | Owner: Agent 6

## Objective
Boost AI/RAG coverage from 23-25% to 70%+

## Your Files (Exclusive)
- `theo/infrastructure/api/app/ai/` (9 files) - 25.5% coverage
- `theo/infrastructure/api/app/ai/rag/` (10 files) - 23.4% coverage
- Tests: `tests/api/ai/` (EXPAND THIS)

## Existing Tests (Study First)
- `tests/api/ai/test_reasoning_modules.py` (27 tests)
- `tests/api/test_ai_router.py` (20 tests)
- `tests/api/test_rag_guardrails_enhanced.py` (30 tests)

## Coverage Gaps
1. RAG pipeline integration
2. Context retrieval edge cases
3. Answer generation error handling
4. Source attribution validation
5. Prompt engineering tests
6. Guardrail enforcement
7. LLM error handling

## Tasks
1. Analyze coverage gaps in AI/RAG modules
2. Add tests for uncovered code paths
3. Create integration tests for RAG pipeline
4. Test error scenarios (API failures, timeouts)
5. Test quality metrics and validation
6. Achieve 70%+ coverage

## Test Areas
```
tests/api/ai/
├── test_rag_pipeline_integration.py (NEW)
├── test_context_retrieval.py (NEW)
├── test_answer_generation.py (NEW)
├── test_prompt_engineering.py (NEW)
└── test_ai_error_handling.py (NEW)
```

## Run Tests
```bash
python -m pytest tests/api/ai/ --cov=theo.services.api.app.ai --cov-report=term-missing
```

## No Conflicts
Separate from: frontend, core, mcp, ingest, retriever packages
