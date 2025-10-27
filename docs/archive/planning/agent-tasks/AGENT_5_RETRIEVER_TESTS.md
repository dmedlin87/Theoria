# Agent Task 5: Retriever/Search Tests

## Priority: HIGH | Time: 2-3 days | Owner: Agent 5

## Objective
Boost `theo/services/api/app/retriever/` coverage from 12.8% to 70%+

## Your Files (Exclusive)
- Directory: `theo/services/api/app/retriever/` (8 files)
- Tests: `tests/api/retriever/` (CREATE THIS)

## Tasks
1. Study retriever source code (8 files)
2. Create test files for: query processing, vector search, keyword search, hybrid search, ranking, reranking
3. Add edge cases: empty queries, special characters, large result sets
4. Add integration tests: end-to-end search flows
5. Achieve 70%+ coverage

## Test Structure
```
tests/api/retriever/
├── test_query_processing.py
├── test_vector_search.py
├── test_hybrid_search.py
├── test_ranking.py
├── test_search_integration.py
└── test_edge_cases.py
```

## Run Tests
```bash
python -m pytest tests/api/retriever/ --cov=theo.infrastructure.api.app.retriever --cov-report=term-missing
```

## No Conflicts
Separate from: frontend, core, mcp, ingest, ai packages
