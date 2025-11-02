# 90% Coverage Strategy for Theoria

**Status:** Active Strategy
**Date:** November 1, 2025
**Target:** 90% coverage for critical packages, 85% overall

## Executive Summary

This strategy expands upon ADR 0003's baseline requirements:

- **80% overall coverage** (baseline requirement)
- **90% critical package coverage** (expanded enforcement)
- **85% overall coverage** (stretch goal)

Current state: **28.3% overall** with critical gaps in core infrastructure (0%), MCP (0%), and key business logic.

**Timeline assumes 50% team capacity** (2 developers half-time, parallel to feature development).

---

## Architecture Requirements

### ADR 0003 Compliance

```text
✅ ≥80% overall coverage (baseline)
✅ ≥90% critical core packages (expanded enforcement)
```

### Critical Package Definition

Packages requiring 90% coverage based on system impact:

| Priority | Package | Current | Target | Impact |
|----------|---------|---------|--------|--------|
| 🚨 CRITICAL | `theo.services.api.app.core` | 0.0% | 90% | Database, settings, runtime |
| 🚨 CRITICAL | `theo.domain` | 81.1% | 90% | Business logic |
| 🚨 CRITICAL | `theo.application` | 82.3% | 90% | Use cases |
| ✅ COMPLIANT | `theo.adapters` | 93.8% | 90% | External integrations |
| ⚠️ HIGH | `theo.services.api.app.ingest` | 16.2% | 90% | Content processing |
| ⚠️ HIGH | `theo.services.api.app.retriever` | 12.8% | 90% | Search functionality |
| ⚠️ HIGH | `theo.services.api.app.ai.rag` | 23.4% | 90% | AI workflows |

---

## Phased Implementation Strategy

### Phase 1: Foundation (Weeks 1-3) - Reach 35% Overall

### Build on existing COVERAGE_ACTION_PLAN.md

#### Week 0: Frontend Test Fixes (Pre-requisite)

### BLOCKING - All other work depends on this

- [ ] **URGENT:** Fix 2 failing frontend test suites blocking coverage measurement
- [ ] Enable frontend coverage reporting and baseline
- [ ] Generate initial coverage.baseline.xml for PR enforcement:

  ```bash
  pytest --cov=theo --cov-report=xml && cp coverage.xml coverage.baseline.xml
  ```

#### Week 1: Critical Infrastructure

- [ ] Core infrastructure tests: `theo.services.api.app.core` (0% → 80%)
  - Database connection lifecycle
  - Settings loading and validation
  - Runtime environment detection
  - Secret migration logic
- [ ] MCP server tests: `theo.services.api.app.mcp` (0% → 80%)
- [ ] Enable basic coverage reporting

#### Week 2: Zero-Coverage Elimination

- [ ] Address all 0% coverage packages
- [ ] Add smoke tests for test directories
- [ ] Establish coverage baseline tracking

#### Week 3: Quick Wins

- [ ] Boost low-hanging fruit packages to 50%+
- [ ] Fix failing test infrastructure
- [ ] Implement coverage dashboard automation

**Expected Outcome:** 35% overall coverage, 0 packages at 0% (Week 3, 4 weeks total including Week 0)

---

### Phase 2: Critical Path Coverage (Weeks 4-8) - Reach 80% Overall

### Execute existing COVERAGE_ACTION_PLAN.md with 90% critical targets

#### Week 4-5: Document Processing Foundation

- [ ] Document parsing edge cases and validation
- [ ] Large file handling and streaming tests
- [ ] Basic ingest pipeline workflow coverage
- [ ] Error handling and recovery mechanisms

#### Week 6-8: Critical Path Packages (Staggered Approach)

- [ ] **Week 6:** `theo.services.api.app.ingest` (16.2% → 90%)
- [ ] **Week 7:** `theo.services.api.app.retriever` (12.8% → 90%)
- [ ] **Week 8:** `theo.services.api.app.ai.rag` (23.4% → 90%)

**Expected Outcome:** 80% overall coverage, critical packages at 85%+

---

### Phase 3: Critical Package Enforcement (Weeks 9-10) - 90% Critical

#### Week 9: Core Package Excellence

- [ ] `theo.services.api.app.core` (80% → 90%)
  - Branch coverage for all conditionals
  - Exception path testing
  - Edge cases in configuration
  - Security boundary testing

#### Week 10: Domain & Application Layers

- [ ] `theo.domain` (81.1% → 90%)
- [ ] `theo.application` (82.3% → 90%)
- [ ] Business rule edge cases
- [ ] Error handling completeness
- [ ] Integration boundary testing

**Expected Outcome:** All critical packages at 90%+, overall 82%

---

### Phase 4: Stretch to Excellence (Weeks 11-12) - 85% Overall

#### Week 11: Comprehensive Coverage

- [ ] Address remaining 50-80% packages
- [ ] API routes comprehensive testing
- [ ] Workflow orchestration coverage
- [ ] Export and analytics completeness

#### Week 12: Quality Gates & Polish

- [ ] Enable CI coverage gates
- [ ] Branch coverage tracking
- [ ] Mutation testing for critical paths
- [ ] Performance benchmark coverage

**Expected Outcome:** 85% overall coverage, all critical packages 90%+

---

## Test Strategy by Coverage Level

### 0% → 60%: Foundation Testing

### Focus: Basic functionality and happy paths

```python
# Template for foundation tests
class TestCoreFunctionality:
    def test_basic_workflow(self):
        """Test primary use case works"""

    def test_error_handling(self):
        """Test appropriate exceptions raised"""

    def test_configuration_defaults(self):
        """Test default configurations"""
```

### 60% → 80%: Comprehensive Testing

### Focus: Edge cases, integration, error scenarios

```python
# Template for comprehensive tests
class TestComprehensiveCoverage:
    @pytest.mark.parametrize("scenario", ["case1", "case2", "edge"])
    def test_multiple_scenarios(self, scenario):
        """Test various input scenarios"""

    def test_integration_dependencies(self):
        """Test with real dependencies"""

    def test_performance_bounds(self):
        """Test performance constraints"""
```

### 80% → 90%: Excellence Testing

### Focus: Branch coverage, mutation testing, security

```python
# Template for excellence tests
class TestExcellenceCoverage:
    def test_all_branch_paths(self):
        """Test every conditional branch"""

    def test_security_boundaries(self):
        """Test security constraints"""

    def test_resource_exhaustion(self):
        """Test system limits and recovery"""
```

---

## Critical Package Test Plans

### `theo.services.api.app.core` (0% → 90%)

**Files requiring coverage:**

- `database.py` - Connection lifecycle, transaction handling
- `settings.py` - Configuration validation, environment detection
- `runtime.py` - Runtime mode switching, feature flags
- `secret_migration.py` - Secret management, migration logic
- `settings_store.py` - Persistence, caching, updates
- `version.py` - Version information, compatibility checks

**Test Strategy:**

```python
# tests/api/core/test_comprehensive.py
class TestDatabaseExcellence:
    def test_connection_lifecycle_all_branches(self):
        """Test every connection state transition"""

    def test_transaction_commit_rollback_scenarios(self):
        """Test all transaction outcomes"""

    def test_pool_exhaustion_recovery(self):
        """Test connection pool limits"""

class TestSettingsExcellence:
    def test_all_environment_combinations(self):
        """Test every environment variable combination"""

    def test_validation_error_messages(self):
        """Test specific validation failures"""
```

### `theo.services.api.app.ingest` (16.2% → 90%)

**Focus Areas:**

- Document parsing edge cases (malformed files, encodings)
- Large file handling (memory limits, streaming)
- Concurrent ingestion (race conditions, locking)
- Pipeline failures (recovery, partial states)
- Metadata enrichment (complex documents, edge cases)

---

## Automation & Tooling

### Coverage Enforcement

```yaml
# .github/workflows/coverage.yml
- name: Verify Critical Coverage
  run: |
    python scripts/security/verify_critical_coverage.py
    # Enforces 90% for critical packages

- name: Overall Coverage Check
  run: |
    python -m pytest --cov=theo --cov-fail-under=80
    # Enforces 80% overall baseline
```

### Coverage Analysis Tools

```bash
# Enhanced coverage reporting
python analyze_coverage.py --detailed --branch-coverage

# Critical package verification
python scripts/security/verify_critical_coverage.py --strict

# Coverage trend analysis
python scripts/coverage/track_trends.py --weeks 12
```

### Dashboard Integration

- **Real-time coverage tracking** in `dashboard/coverage-dashboard.md`
- **Package-level heatmaps** for critical components
- **Trend analysis** with weekly progress reports
- **Automated alerts** for coverage regressions

---

## PR Coverage Policy

### During Implementation (Weeks 1-12)

**No Regression Policy:**

- **PRs cannot decrease coverage** for any package currently above its target
- **New code must maintain current coverage levels** in modified files
- **Critical packages require 90% coverage** for any new changes
- **Overall project coverage cannot drop** below 28.3% baseline

**Enforcement:**

```yaml
# .github/workflows/pr-coverage.yml
- name: PR Coverage Check
  run: |
    python scripts/coverage/pr_coverage_check.py
    # Blocks PRs that reduce coverage
```

**Exceptions:**

- Critical bug fixes may temporarily reduce coverage with explicit approval
- Infrastructure changes require compensating test coverage within 1 week
- New features must include tests to maintain overall coverage percentage

---

## Quality Gates

### CI/CD Integration

```python
# scripts/enforcement/coverage_gates.py
CRITICAL_THRESHOLDS = {
    "theo.services.api.app.core": 0.90,
    "theo.domain": 0.90,
    "theo.application": 0.90,
    "theo.services.api.app.ingest": 0.90,
    "theo.services.api.app.retriever": 0.90,
    "theo.services.api.app.ai.rag": 0.90,
}

OVERALL_THRESHOLD = 0.80  # Baseline from ADR 0003
STRETCH_THRESHOLD = 0.85  # Stretch goal
```

### Branch Protection Rules

- **PR must maintain 90% coverage** for modified critical packages
- **Overall coverage cannot decrease** below current baseline
- **New packages require 80% coverage** before merge
- **Critical bug fixes require comprehensive test coverage**

---

## Success Metrics

### Coverage Targets by Phase

| Phase | Overall | Critical Packages | Status |
|-------|---------|-------------------|--------|
| Phase 1 (Week 3) | 35% | 60% | 🟡 Foundation |
| Phase 2 (Week 8) | 80% | 85% | 🟢 Baseline |
| Phase 3 (Week 10) | 82% | 90% | 🟢 ADR Compliant |
| Phase 4 (Week 12) | 85% | 90% | 🟢 Excellence |

### Quality Metrics

- **Branch Coverage:** ≥85% for critical packages
- **Mutation Score:** ≥80% for core business logic
- **Test Execution Time:** ≤5 minutes for unit suite
- **Integration Coverage:** ≥75% for API contracts

---

## Risk Mitigation

### Technical Risks

- **Test Flakiness:** Implement retry logic and deterministic fixtures
- **Performance Impact:** Use test splitting and parallel execution
- **Coverage Inflation:** Exclude generated code and test utilities
- **Maintenance Burden:** Automate test generation where possible

### Timeline Risks

- **Scope Creep:** Phase-based approach with clear gates
- **Resource Constraints:** Prioritize critical packages first
- **Technical Debt:** Address coverage alongside feature development
- **Team Adoption:** Provide comprehensive documentation and tools

---

## Documentation & Training

### Developer Guidelines

- **Testing Standards:** Updated `CONTRIBUTING.md` with 90% requirements
- **Test Templates:** Comprehensive templates for each coverage tier
- **Best Practices:** Security testing, performance testing, edge cases
- **Tool Usage:** Coverage analysis, reporting, and enforcement tools

### Team Resources

- **Coverage Champions:** Designated coverage advocates per team
- **Weekly Reviews:** Coverage progress and blocker discussions
- **Training Sessions:** Advanced testing techniques and tools
- **Documentation:** Living documentation with examples and patterns

---

## Related Documentation

- **ADR 0003:** Testing and coverage requirements
- **COVERAGE_ACTION_PLAN.md:** Archived 80% implementation plan (Oct 2025) - **superseded by this strategy**
- **COVERAGE_REVIEW.md:** Comprehensive coverage analysis
- **TEST_MAP.md:** Test inventory and strategy
- **verify_critical_coverage.py:** Critical package enforcement

---

## Next Steps

1. Review strategy with engineering leadership
2. Assign Phase 1 tasks and owners
3. Set up automated coverage tracking
4. Schedule weekly progress reviews
5. Begin critical infrastructure testing

---

**Status Review:** Weekly during Phase 1-2, biweekly during Phase 3-4
**Strategy Owner:** Engineering Team Lead
**Last Updated:** November 1, 2025
