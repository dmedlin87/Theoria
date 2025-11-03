# Theoria Simplification Plan - Removing Complex Low-Value Features

**Created:** November 2, 2025  
**Status:** Planning Phase  
**Estimated Effort:** 3-4 PRs over 1-2 weeks

## Overview

This document outlines the removal of complex features that add maintenance overhead without proportional value. The goal is to reduce codebase complexity, improve maintainability, and focus development efforts on core theological research and AI capabilities.

## Features Targeted for Removal

### 1. MCP Server (HIGH PRIORITY)
**Path:** `mcp_server/`  
**Complexity:** ~10 files, custom protocol implementation  
**Rationale:** Originally intended for ChatGPT app connectors, but adds significant infrastructure complexity for uncertain adoption.

**Files to Remove:**
```
mcp_server/
├── server.py (10K+ lines)
├── schemas.py (22K+ lines) 
├── security.py (10K+ lines)
├── middleware.py (6K+ lines)
├── metrics.py (5K+ lines)
├── validators.py (7K+ lines)
├── config.py (3K+ lines)
├── errors.py (5K+ lines)
├── Dockerfile
├── __init__.py
├── __main__.py
└── tools/ (directory)
```

**Dependencies to Clean:**
- Remove MCP-related dependencies from `pyproject.toml`
- Remove MCP server from Docker compose configurations
- Remove MCP-related environment variables from `.env.example`
- Clean up any import references in main application

### 2. Evidence System (COMPLETED)
**Path:** `theo/evidence/`
**Complexity:** 10 specialized modules, complex citation/validation workflows
**Rationale:** Specialized system that may be over-engineered for current research needs.
**Outcome:** Package removed in favour of `scripts/evidence_tool.py`, a lightweight helper for JSON/JSONL datasets.

**Files to Remove:**
```
theo/evidence/
├── __init__.py
├── citations.py
├── cli.py (11K+ lines)
├── dossier.py (9K+ lines)
├── indexer.py (5K+ lines)
├── models.py (4K+ lines)
├── normalization.py
├── promoter.py
├── utils.py (12K+ lines)
└── validator.py (3K+ lines)
```

**Impact Assessment Needed:**
- Audit main application for evidence system usage
- Check if any API endpoints depend on evidence features
- Identify alternative approaches for citation management

### 3. Complex Checkpoint System (MEDIUM PRIORITY)  
**Path:** `theo/checkpoints.py`  
**Complexity:** 350+ lines with version migrations, atomic operations  
**Rationale:** Could be replaced with simpler persistence patterns.

**Files to Remove:**
```
theo/checkpoints.py
```

**Migration Strategy:**
- Identify current checkpoint usage in embedding rebuild processes
- Replace with simpler state persistence (JSON files, database records)
- Remove version migration complexity

### 4. Platform Event System (LOW PRIORITY)
**Path:** `theo/platform/`  
**Complexity:** Event-driven architecture abstraction  
**Rationale:** May be over-engineering; evaluate if simpler patterns suffice.

**Files to Evaluate:**
```
theo/platform/
├── __init__.py
├── application.py (11K+ lines)
├── bootstrap.py
└── events/ (directory)
```

## Implementation Plan

### Phase 1: MCP Server Removal (Week 1)
**PR 1: Remove MCP Infrastructure**
- [ ] Delete entire `mcp_server/` directory
- [ ] Remove MCP dependencies from `pyproject.toml`
- [ ] Remove MCP Docker configurations
- [ ] Clean `infra/docker-compose.yml`
- [ ] Update `.env.example`
- [ ] Remove MCP-related tests from `tests/mcp_tools/`

### Phase 2: Evidence System Evaluation & Removal (Week 1-2)
**PR 2: Audit Evidence System Usage**
- [x] Search codebase for evidence system imports
- [x] Document current usage patterns
- [x] Identify API endpoints using evidence features
- [x] Plan migration path for essential functionality

**PR 3: Remove Evidence System**
- [x] Delete `theo/evidence/` directory
- [x] Remove evidence-related routes/endpoints
- [x] Update documentation
- [x] Migrate essential citation functionality to simpler approach

### Phase 3: Checkpoint System Simplification (Week 2)
**PR 4: Simplify Checkpoints**
- [ ] Audit current checkpoint usage
- [ ] Implement simpler state persistence
- [ ] Remove version migration complexity
- [ ] Delete `theo/checkpoints.py`
- [ ] Update embedding rebuild processes

### Phase 4: Platform Events Evaluation (Future)
**Future Consideration:**
- Evaluate `theo/platform/` directory usage
- Determine if event system provides value
- Consider removal if simple function calls suffice

## Risk Mitigation

### Before Each Removal:
1. **Usage Audit**: Search entire codebase for imports and references
2. **Test Coverage**: Run full test suite to identify dependencies
3. **Backup Branch**: Create feature branch before deletion
4. **Incremental Approach**: Remove in small, reviewable chunks

### Documentation Updates Required:
- [ ] Update README.md to remove references to removed features
- [ ] Update API documentation
- [ ] Update deployment guides
- [ ] Update development setup instructions

## Expected Benefits

### Immediate Benefits:
- **Reduced codebase size**: ~50K+ lines removed
- **Simplified dependencies**: Fewer external packages to maintain
- **Cleaner architecture**: Less cognitive overhead for new developers
- **Faster CI/CD**: Fewer tests and builds to run

### Long-term Benefits:
- **Easier maintenance**: Focus on core functionality
- **Reduced security surface**: Less code to secure and audit
- **Clearer development path**: Less distraction from main features
- **Faster onboarding**: Simpler codebase for new contributors

## Rollback Plan

If any removed feature proves essential:

1. **Git Recovery**: Features can be restored from git history
2. **Selective Restoration**: Cherry-pick specific functionality if needed
3. **Simplified Reimplementation**: Reimplement with lessons learned

## Future MCP Implementation

**If MCP server is needed later:**

### Simplified Approach:
- Use existing MCP libraries instead of custom implementation
- Implement only essential tools initially
- Consider serverless/cloud functions instead of complex server
- Start with basic HTTP endpoints, add MCP protocol later

### Implementation Strategy:
- Begin with simple FastAPI endpoints
- Add MCP protocol layer only when needed
- Use proven libraries (e.g., `mcp` package) instead of custom implementation
- Focus on specific use cases rather than generic infrastructure

## Success Metrics

- [ ] Codebase size reduction: Target 30%+ reduction in total lines
- [ ] Test execution time: Target 20%+ improvement in CI/CD speed  
- [ ] Dependency count: Target 25%+ reduction in external packages
- [ ] Developer onboarding: Simpler setup and explanation
- [ ] Maintenance velocity: Faster feature development without complexity overhead

## Notes

This simplification aligns with the "worse is better" philosophy - focusing on core functionality that works well rather than comprehensive features that add complexity. The removed features can always be re-added later with better understanding of actual requirements and simpler implementations.

---

**Next Steps:**
1. Create feature branch for MCP removal
2. Run comprehensive usage audit 
3. Begin Phase 1 implementation
4. Update this document with progress and findings