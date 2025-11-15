# Theoria Test Coverage - Detailed Gaps & Files Requiring Tests

## Critical Gap Analysis: File-by-File Breakdown

### 1. API Routes (20+ files, ~10-15% coverage)

#### Zero Test Coverage (6 files):
```
/home/user/Theoria/theo/infrastructure/api/app/routes/creators.py
  - Creator-related endpoints (CRUD operations for researcher profiles)
  - Endpoints: likely POST /creators, GET /creators/{id}, PUT, DELETE
  - Missing: Authorization, validation, error handling tests

/home/user/Theoria/theo/infrastructure/api/app/routes/jobs.py
  - Job/task management endpoints
  - Endpoints: job status, job tracking, progress monitoring
  - Missing: All test coverage

/home/user/Theoria/theo/infrastructure/api/app/routes/trails.py
  - Research trails/breadcrumbs endpoints
  - Endpoints: query history, analysis trails, workflow tracking
  - Missing: All test coverage

/home/user/Theoria/theo/infrastructure/api/app/routes/features.py
  - Feature flag endpoints and availability checks
  - Endpoints: GET /features, feature toggles
  - Missing: All test coverage

/home/user/Theoria/theo/infrastructure/api/app/routes/export/zotero.py
  - Zotero export integration (Critical - external service)
  - Endpoints: POST /export/zotero, sync operations
  - Missing: Integration tests, error handling, authentication

/home/user/Theoria/theo/infrastructure/api/app/routes/export/deliverables.py
  - Export deliverables in multiple formats
  - Endpoints: POST /export/deliverables, GET /exports/{id}
  - Missing: Format validation, large file handling, error cases
```

#### Minimal/Partial Coverage (3 files):
```
/home/user/Theoria/theo/infrastructure/api/app/routes/research.py
  - Research workflow endpoints
  - Current Status: ~20% coverage
  - Missing: Complex workflow paths, hypothesis validation, edge cases

/home/user/Theoria/theo/infrastructure/api/app/routes/notebooks.py
  - Notebook creation, editing, sharing
  - Current Status: ~25% coverage
  - Missing: Concurrent editing conflicts, permission checks, versioning

/home/user/Theoria/theo/infrastructure/api/app/routes/analytics.py
  - Analytics and metrics endpoints
  - Current Status: ~15% coverage
  - Missing: Data aggregation edge cases, time range filtering, permissions
```

---

### 2. MCP Server Implementation (0% coverage - Critical)

```
/home/user/Theoria/mcp_server/__main__.py (0 tests)
  - Entry point for MCP protocol server
  - Required Tests:
    ✗ Server initialization and startup
    ✗ Graceful shutdown
    ✗ Request routing
    ✗ Error handling and error codes
    ✗ Protocol compliance (JSON-RPC, capabilities)
    ✗ Tool invocation
    ✗ Resource exposure
    ✗ Prompt handling
    ✗ Logging and metrics

/home/user/Theoria/mcp_server/__init__.py (0 tests)
  - Package initialization and exports
  - Required Tests:
    ✗ Import correctness
    ✗ Public API surface validation
    ✗ Version/compatibility checks

/home/user/Theoria/mcp_server/config.py (86% coverage but gaps remain)
  - Configuration parsing and validation
  - Current Issues:
    ✗ _parse_int error paths (33% coverage)
    ✗ _parse_list error paths (67% coverage)
    ✗ Invalid configuration scenarios
    ✗ Environment variable override cases
    ✗ Type coercion edge cases

/home/user/Theoria/mcp_server/errors.py (75% coverage)
  - MCP error definitions and handlers
  - Current Gaps:
    ✗ AuthenticationError.__init__ (0% coverage)
    ✗ AuthorizationError.__init__ (0% coverage)
    ✗ RateLimitError.__init__ (0% coverage)
    ✗ mcp_error_handler (0% coverage)
    ✗ generic_error_handler (0% coverage)
    ✗ Error message formatting
    ✗ Stack trace handling

/home/user/Theoria/mcp_server/middleware.py (67% coverage)
  - Request/response middleware
  - Current Gaps:
    ✗ CORSHeaderMiddleware (0% coverage - 7 methods untested)
    ✗ RequestLimitMiddleware.dispatch (40% coverage)
    ✗ Rate limiting edge cases
    ✗ CORS header validation
    ✗ Request ID propagation
    ✗ Timing middleware edge cases

/home/user/Theoria/mcp_server/metrics.py (70% coverage)
  - Metrics collection and reporting
  - Current Gaps:
    ✗ ToolMetrics.avg_duration_ms (0% coverage)
    ✗ ToolMetrics.success_rate (0% coverage)
    ✗ MetricsCollector.get_metrics_summary (0% coverage)
    ✗ MetricsCollector.reset (0% coverage)
    ✗ reset_metrics_collector (0% coverage)
    ✗ Metrics aggregation edge cases
```

---

### 3. Infrastructure API Models (2,647 LOC, <5% coverage)

#### Zero Test Coverage (5 files):
```
/home/user/Theoria/theo/infrastructure/api/app/models/ai.py
  - AI-related request/response models
  - Untested Models: (likely ~15-20 model classes)
    ✗ Chat request/response models
    ✗ Completion models
    ✗ Token counting models
    ✗ Streaming response models
    ✗ Error response models
  - Missing: Type validation, field validation, serialization

/home/user/Theoria/theo/infrastructure/api/app/models/reasoning.py
  - Reasoning engine request/response models
  - Untested Models: (likely ~10-15 model classes)
    ✗ Reasoning step models
    ✗ Conclusion models
    ✗ Chain-of-thought models
    ✗ Inference models
  - Missing: Logic validation, constraint checking

/home/user/Theoria/theo/infrastructure/api/app/models/analytics.py
  - Analytics and telemetry models
  - Untested Models: (likely ~10-15 model classes)
    ✗ Event tracking models
    ✗ Metrics models
    ✗ Aggregation models
    ✗ Report models
  - Missing: Aggregation validation, time-series validation

/home/user/Theoria/theo/infrastructure/api/app/models/research_plan.py
  - Research plan models
  - Untested Models: (likely ~8-12 model classes)
    ✗ Plan definition models
    ✗ Step models
    ✗ Task models
    ✗ Progress models
  - Missing: Workflow validation, dependency checking

/home/user/Theoria/theo/infrastructure/api/app/models/watchlists.py
  - Watchlist management models
  - Untested Models: (likely ~5-8 model classes)
    ✗ Watchlist definition models
    ✗ Item models
    ✗ Alert models
  - Missing: Constraint validation, permission models
```

#### Partial Coverage (<25%):
```
/home/user/Theoria/theo/infrastructure/api/app/models/transcripts.py
  - Transcript models (audio/video transcripts)
  - Current Status: ~20% coverage
  - Missing: Speaker identification, timestamp validation, format conversion

/home/user/Theoria/theo/infrastructure/api/app/models/jobs.py
  - Job/task models
  - Current Status: ~25% coverage
  - Missing: State machine validation, retry logic validation

/home/user/Theoria/theo/infrastructure/api/app/models/notebooks.py
  - Notebook and cell models
  - Current Status: ~30% coverage
  - Missing: Cell execution order, markdown validation, code validation

/home/user/Theoria/theo/infrastructure/api/app/models/trails.py
  - Audit trail and history models
  - Current Status: ~15% coverage
  - Missing: Temporal validation, causality checking

/home/user/Theoria/theo/infrastructure/api/app/models/base.py
  - Base model definitions
  - Current Status: ~50% coverage
  - Missing: Custom validators, edge case serialization
```

---

### 4. Frontend Components (191 files, ~17% coverage)

#### Components with Zero/Minimal Tests:

**Search Interface** (12+ components):
```
theo/services/web/app/search/
  ├── SearchBox.tsx               - Search input component
  ├── SearchResults.tsx           - Results display
  ├── FilterPanel.tsx             - Advanced filters
  ├── FacetedSearch.tsx           - Faceted navigation
  ├── SearchMetrics.tsx           - Search stats
  └── (8 more components)
  
Missing: User interactions, filter combinations, large result sets, error states
```

**Research Workspace** (15+ components):
```
theo/services/web/app/research/
  ├── ResearchCanvas.tsx          - Main workspace
  ├── DocumentPanel.tsx           - Document viewer
  ├── AnnotationTools.tsx         - Annotation interface
  ├── VerseLinker.tsx             - Verse reference linking
  ├── CollaborationPanel.tsx      - Multi-user features
  └── (10 more components)
  
Missing: Complex workflows, concurrent editing, permission checks, persistence
```

**Notebook Editor** (10+ components):
```
theo/services/web/app/notebooks/
  ├── NotebookEditor.tsx          - Main editor
  ├── CellEditor.tsx              - Individual cells
  ├── CellControls.tsx            - Cell operations
  ├── CellOutput.tsx              - Output rendering
  ├── NotebookToolbar.tsx         - Editor toolbar
  └── (5 more components)
  
Missing: Concurrent editing, execution, versioning, sharing
```

**Copilot Integration** (8+ components):
```
theo/services/web/app/copilot/
  ├── CopilotChat.tsx             - Chat interface
  ├── ContextSelector.tsx         - Context management
  ├── ResponseRenderer.tsx        - AI response display
  ├── StreamingIndicator.tsx      - Loading states
  └── (4 more components)
  
Missing: Streaming responses, context handling, error states, rate limiting
```

**Dashboard Components** (20+ components with partial coverage):
```
theo/services/web/app/dashboard/components/
  ├── ActivityFeed.tsx            - Activity timeline
  ├── MetricsGrid.tsx             - Metrics display
  ├── RecentActivity.tsx          - Recent items
  ├── ProfileSummary.tsx          - User profile
  ├── SystemHealthCard.tsx        - System status
  ├── QuickStats.tsx              - Statistics
  ├── QuickActions.tsx            - Action buttons
  └── (13 more components)
  
Current: Some coverage, Missing: Error states, edge cases, accessibility
```

**Verse Components** (10+ components):
```
theo/services/web/app/verse/[osis]/
  ├── VerseGraphSection.tsx       - Graph visualization
  ├── ReliabilityOverviewCard.tsx - Reliability display
  ├── VerseSkeletons.tsx          - Loading skeletons
  └── (7 more)
  
Missing: Large graphs, real-time updates, interactive features
```

---

### 5. GraphQL Implementation (5 files, ~40% coverage)

```
/home/user/Theoria/theo/infrastructure/api/app/graphql/
  ├── schema.py                   - GraphQL schema definition
  │   Current: ~50% coverage
  │   Missing: Complex type definitions, union/interface tests
  │
  ├── resolvers/                  - Resolver implementations
  │   Current: ~35% coverage
  │   Missing: Authorization checks, permission validation, N+1 query patterns
  │
  ├── types.py                    - Type definitions
  │   Current: ~40% coverage
  │   Missing: Input validation, custom scalar tests
  │
  └── middleware.py               - GraphQL middleware
      Current: ~30% coverage
      Missing: Authentication, error handling, request logging
```

---

### 6. Event & Pub/Sub Systems (Limited coverage)

```
/home/user/Theoria/theo/adapters/events/
  
redis.py (15% coverage):
  - Redis event publishing
  Missing:
    ✗ Publish/subscribe workflow
    ✗ Message serialization
    ✗ Connection failure handling
    ✗ Subscriber error recovery
    ✗ Message ordering validation

kafka.py (10% coverage):
  - Kafka event integration
  Missing:
    ✗ Topic management
    ✗ Consumer groups
    ✗ Offset management
    ✗ Dead letter queue handling
    ✗ Partition distribution
```

---

### 7. Secret Management Adapters (0% coverage)

```
/home/user/Theoria/theo/adapters/secrets/

vault.py (0 tests):
  - HashiCorp Vault integration
  Missing:
    ✗ Authentication
    ✗ Secret retrieval
    ✗ Lease renewal
    ✗ Error handling
    ✗ Fallback strategies

aws.py (0 tests):
  - AWS Secrets Manager integration
  Missing:
    ✗ Secret retrieval
    ✗ Rotation handling
    ✗ IAM authentication
    ✗ Region handling
    ✗ Error recovery
```

---

### 8. Graph Adapters (Limited coverage)

```
/home/user/Theoria/theo/adapters/graph/

  All files: ~15% coverage
  Missing:
    ✗ Graph construction
    ✗ Relationship validation
    ✗ Query optimization
    ✗ Traversal performance
    ✗ Cycle detection
```

---

### 9. Error Handling & Recovery (59% of exception files have partial coverage)

```
/home/user/Theoria/theo/infrastructure/api/app/error_handlers.py
  Current: Minimal coverage
  Missing:
    ✗ All HTTPException path handlers
    ✗ Validation error formatting
    ✗ Authentication error responses
    ✗ Authorization error responses
    ✗ Rate limit error responses
    ✗ Server error handling
    ✗ Error message localization
    ✗ Stack trace handling (development vs production)
```

---

## Test Coverage Matrix

### Files by Coverage Level

#### 0% Coverage (11 files):
- `mcp_server/__main__.py`
- `mcp_server/__init__.py`
- `theo/infrastructure/api/app/routes/creators.py`
- `theo/infrastructure/api/app/routes/jobs.py`
- `theo/infrastructure/api/app/routes/trails.py`
- `theo/infrastructure/api/app/routes/features.py`
- `theo/infrastructure/api/app/models/ai.py`
- `theo/infrastructure/api/app/models/reasoning.py`
- `theo/infrastructure/api/app/models/analytics.py`
- `theo/infrastructure/api/app/models/research_plan.py`
- `theo/infrastructure/api/app/models/watchlists.py`

#### 1-25% Coverage (15 files):
- `theo/adapters/secrets/vault.py`
- `theo/adapters/secrets/aws.py`
- `theo/adapters/events/kafka.py`
- `theo/adapters/events/redis.py`
- `theo/adapters/graph/` (all files)
- `theo/infrastructure/api/app/routes/export/zotero.py`
- `theo/infrastructure/api/app/routes/export/deliverables.py`
- `theo/infrastructure/api/app/error_handlers.py`
- `theo/infrastructure/api/app/versioning.py`
- `theo/infrastructure/api/app/models/transcripts.py`
- `theo/infrastructure/api/app/models/trails.py`
- Multiple frontend components

#### 25-50% Coverage (20+ files):
- `theo/infrastructure/api/app/models/notebooks.py`
- `theo/infrastructure/api/app/models/jobs.py`
- `theo/infrastructure/api/app/routes/research.py`
- `theo/infrastructure/api/app/routes/notebooks.py`
- `theo/infrastructure/api/app/routes/analytics.py`
- `theo/infrastructure/api/app/graphql/` (multiple files)
- Multiple frontend components

---

## Next Actions by Priority

### Priority 1: CRITICAL (This Week)
1. Create test suite for MCP server (0% coverage)
2. Add route tests for creators, jobs, trails, features
3. Add basic model validation tests for ai, reasoning, analytics, research_plan

### Priority 2: HIGH (This Sprint)
4. Complete route tests for all export functions
5. Add frontend component unit tests (focus on critical workflows)
6. Complete error handler tests

### Priority 3: MEDIUM (Next Sprint)
7. Add secret manager tests
8. Add event system tests
9. Expand GraphQL resolver tests

---

**Total Test Gap**: ~350+ test functions need to be added to achieve 80% coverage
**Estimated Effort**: 145-165 hours (4-5 weeks)

