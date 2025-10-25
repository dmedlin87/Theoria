# Documentation Index

> **Last Updated:** October 2025

This index provides a navigational overview of all Theoria documentation, organized by topic and audience.

## 📋 Table of Contents

- [Getting Started](#getting-started)
- [Development](#development)
- [Agents](#agents)
- [Features](#features)
- [Architecture](#architecture)
- [Operations](#operations)
- [Security](#security)
- [Testing](#testing)
- [Archived Documentation](#archived-documentation)

---

## Getting Started

**For new users and contributors:**

- [README.md](../README.md) - Project overview and quick start
- [START_HERE.md](../START_HERE.md) - PowerShell launcher guide
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines and toolchain
- [docs/agents/implementation-guide.md](../agents/implementation-guide.md) - AI scaffolding and implementation patterns

## Development

### API Documentation
- [docs/development/api-reference.md](../development/api-reference.md) - FastAPI endpoints and authentication
- [docs/development/authentication.md](../development/authentication.md) - Auth configuration (API keys, JWT, anonymous)
- [docs/development/cli-reference.md](../development/cli-reference.md) - Command-line interface reference

### Data Processing
- [docs/development/chunking.md](../development/chunking.md) - Document chunking strategies
- [docs/development/frontmatter.md](../development/frontmatter.md) - Metadata extraction from frontmatter
- [docs/development/osis.md](../development/osis.md) - Scripture reference normalization

### UI Development
- [docs/development/ui-guidelines.md](../development/ui-guidelines.md) - Design system and component patterns
- [docs/features/ux/navigation-loading-improvements.md](../features/ux/navigation-loading-improvements.md) - Navigation and loading best practices
- [theo/services/web/tests/README.md](../theo/services/web/tests/README.md) - Frontend testing guide
- [theo/services/web/public/keyboard-shortcuts.md](../theo/services/web/public/keyboard-shortcuts.md) - Keyboard shortcuts reference

### Code Quality
- [docs/development/typing-standards.md](../development/typing-standards.md) - TypeScript and Python typing conventions
- [docs/development/debugging-guide.md](../development/debugging-guide.md) - Debugging strategies and tools
- [mypy.ini](../mypy.ini), [mypy_mcp.ini](../mypy_mcp.ini) - Type checking configuration

## Agents

- [docs/agents/prompting-guide.md](../agents/prompting-guide.md) - Comprehensive guide to agent architecture and prompting strategies
- [docs/agents/thinking-enhancement.md](../agents/thinking-enhancement.md) - Agent reasoning improvements (full design doc)
- [docs/agents/system-prompt.md](../agents/system-prompt.md) - System prompt engineering (TRO master prompt)
- [docs/agents/implementation-guide.md](../agents/implementation-guide.md) - Step-by-step implementation guide for reasoning framework
- [docs/agents/confinement.md](../agents/confinement.md) - Security framework for AI agents
- [docs/agents/mcp-integration-guide.md](../agents/mcp-integration-guide.md) - Model Context Protocol integration
- [docs/adr/0001-expose-theoria-via-mcp.md](../adr/0001-expose-theoria-via-mcp.md) - ADR: MCP exposure decision
- [docs/adr/0001-mcp-tools-and-apps-sdk.md](../adr/0001-mcp-tools-and-apps-sdk.md) - ADR: MCP tools and SDK

## Features

### Discovery Feed
- [docs/features/discovery/overview.md](../features/discovery/overview.md) - Complete feature specification
- [docs/features/discovery/quick-start.md](../features/discovery/quick-start.md) - Quick start guide for discoveries
- [docs/features/discovery/scheduler.md](../features/discovery/scheduler.md) - Background scheduler plan
- [docs/features/discovery/trend-anomaly-detector-research.md](../features/discovery/trend-anomaly-detector-research.md) - Research blueprint for trend/anomaly maturity
- [docs/features/discovery/contradiction-detection.md](../features/discovery/contradiction-detection.md) - Contradiction signal design

### Case Builder
- [docs/features/case-builder/overview.md](../features/case-builder/overview.md) - Consolidated specification and roadmap
- [docs/features/case-builder/case-builder.schema.json](../features/case-builder/case-builder.schema.json) - Case Builder JSON schema
- [docs/archive/planning/case-builder/](../archive/planning/case-builder/) - Historical versions (v1-v4)

### Future Features & Roadmaps
- [docs/features/roadmap/roadmap.md](../features/roadmap/roadmap.md) - Cognitive Scholar roadmap
- [docs/features/roadmap/future-features-roadmap.md](../features/roadmap/future-features-roadmap.md) - 25 planned features with priority matrix
- [docs/features/roadmap/more-features.md](../features/roadmap/more-features.md) - Additional feature ideas
- [docs/features/roadmap/incomplete-features.md](../features/roadmap/incomplete-features.md) - Incomplete or pending capabilities
- [docs/features/roadmap/strategic-roadmap.pdf](../features/roadmap/strategic-roadmap.pdf) - Strategic roadmap (PDF)

### UX & Research
- [docs/features/ux/navigation-loading-improvements.md](../features/ux/navigation-loading-improvements.md) - Navigation and loading improvements
- [docs/features/ux/ui-overhaul-proposal.md](../features/ux/ui-overhaul-proposal.md) - UI overhaul proposal
- [docs/features/ux/ux-review.md](../features/ux/ux-review.md) - UX review summary
- [docs/features/ux/ux-improvements-2025-10-16.md](../features/ux/ux-improvements-2025-10-16.md) - UX improvement session
- [docs/features/memory/memory-system-upgrade.md](../features/memory/memory-system-upgrade.md) - Memory system upgrade plan
- [docs/features/research/reranker-mvp.md](../features/research/reranker-mvp.md) - Reranker MVP proposal

## Architecture

### System Design
- [docs/architecture/clean-architecture.md](../architecture/clean-architecture.md) - Complete system architecture and build spec
- [docs/architecture/codebase-review.md](../architecture/codebase-review.md) - Architectural analysis and patterns
- [docs/adr/0001-hexagonal-architecture.md](../adr/0001-hexagonal-architecture.md) - ADR: Hexagonal/ports-and-adapters pattern
- [docs/architecture/modularity-plan.md](../architecture/modularity-plan.md) - Module boundaries and organization
- [docs/architecture/modularity-refactor-plan.md](../architecture/modularity-refactor-plan.md) - Modularization strategy

### Technical Specifications
- [docs/architecture/improvements.md](../architecture/improvements.md) - Architecture improvement roadmap
- [docs/architecture/migration-example.md](../architecture/migration-example.md) - Architecture migration example
- [docs/architecture/review.md](../architecture/review.md) - Architecture review summary
- [docs/architecture/dependency-boundaries.md](../architecture/dependency-boundaries.md) - Dependency boundaries and enforcement

## Operations

### Deployment
- [docs/operations/deployment-overview.md](../operations/deployment-overview.md) - Container builds and signing
- [docs/operations/secrets-backed-configuration.md](../operations/secrets-backed-configuration.md) - Secrets-backed configuration
- [.github/workflows/](../.github/workflows/) - CI/CD workflows
- [docs/operations/production-readiness-gaps.md](../operations/production-readiness-gaps.md) - Pre-production checklist

### Service Management & Reliability
- [start-theoria.ps1](../start-theoria.ps1) - Service launcher script
- [scripts/RUN_SCRIPTS_README.md](../scripts/RUN_SCRIPTS_README.md) - Orchestrator scripts
- [metrics/README.md](../metrics/README.md) - Prometheus metrics
- [docs/operations/service-management.md](../operations/service-management.md) - Service orchestration and management
- [docs/operations/performance.md](../operations/performance.md) - Performance benchmarks and optimization
- [docs/runbooks/performance_discrepancy_runbook.md](../runbooks/performance_discrepancy_runbook.md) - Performance troubleshooting
- [docs/operations/telemetry.md](../operations/telemetry.md) - OpenTelemetry instrumentation
- [docs/operations/release-notes.md](../operations/release-notes.md) - Release highlights

### Monitoring & Dashboards
- [dashboard/coverage-dashboard.md](../dashboard/coverage-dashboard.md) - Test coverage dashboard
- [docs/dashboards/ui-quality-dashboard.md](../dashboards/ui-quality-dashboard.md) - UI quality metrics
- [.lighthouseci/baseline/README.md](../.lighthouseci/baseline/README.md) - Lighthouse baseline thresholds
- [docs/operations/lighthouse-ci.md](../operations/lighthouse-ci.md) - Lighthouse CI integration and thresholds
- [docs/operations/lighthouse-enhancements.md](../operations/lighthouse-enhancements.md) - Lighthouse enhancement log
- [docs/operations/lighthouse-fix.md](../operations/lighthouse-fix.md) - Lighthouse fix summary
- [docs/operations/lighthouse-ci-fix-2025-10-16.md](../operations/lighthouse-ci-fix-2025-10-16.md) - Lighthouse CI fix playbook

## Security

### Policies & Threat Model
- [SECURITY.md](../SECURITY.md) - Security policy and disclosure process
- [THREATMODEL.md](../THREATMODEL.md) - Comprehensive threat model
- [docs/security/red-team.md](../security/red-team.md) - Red team findings and mitigations
- [docs/security/audit-mode-spec.md](../security/audit-mode-spec.md) - Audit mode specification

### Data & Repository Health
- [docs/security/repo-health.md](../security/repo-health.md) - Repository health analysis
- [docs/agents/confinement.md](../agents/confinement.md) - MCP agent security framework
- [data/seeds/](../data/seeds/) - Seed data for testing

## Testing

### Testing Strategy
- [docs/testing/TEST_MAP.md](../testing/TEST_MAP.md) - Comprehensive test map
- [docs/testing/ui-quality-gates.md](../testing/ui-quality-gates.md) - UI quality gate criteria
- [docs/testing/test-database-schema-issue.md](../testing/test-database-schema-issue.md) - Test database schema issue analysis
- [docs/testing/test-database-fix-summary.md](../testing/test-database-fix-summary.md) - Test database fix summary
- [docs/testing/test-suite-issues.md](../testing/test-suite-issues.md) - Known test suite issues
- [docs/testing/test-failure-analysis-2025-10-16.md](../testing/test-failure-analysis-2025-10-16.md) - Failure analysis session notes
- [test-ui-enhancements.md](../test-ui-enhancements.md) - UI enhancement testing guide
- [theo/services/web/tests/README.md](../theo/services/web/tests/README.md) - Frontend test guide

### Contract Testing
- [contracts/schemathesis.toml](../contracts/schemathesis.toml) - API contract configuration

### Test Fixtures
- [fixtures/case_builder/](../fixtures/case_builder/) - Case Builder test data
- [fixtures/citations/](../fixtures/citations/) - Citation formatting examples
- [fixtures/html/](../fixtures/html/), [fixtures/markdown/](../fixtures/markdown/), [fixtures/pdf/](../fixtures/pdf/) - Parser fixtures

## Archived Documentation

**Historical documents preserved for reference:**

- [docs/archive/README.md](../archive/README.md) - Archive overview and retention policy
- [docs/archive/2025-10/](../archive/2025-10/) - October 2025 session summaries
- [docs/archive/fixes/](../archive/fixes/) - Resolved bug fix reports
- [docs/archive/audits/](../archive/audits/) - Historical audit snapshots
- [docs/archive/planning/](../archive/planning/) - Completed planning documents
- [docs/archive/ui-sessions/](../archive/ui-sessions/) - UI/UX refactoring session notes

---

## Document Organization Principles

1. **Root-level docs** - User-facing guides (README, CONTRIBUTING, SECURITY, etc.)
2. **docs/** - Technical documentation, specifications, and guides grouped by topic
3. **docs/adr/** - Architecture Decision Records
4. **docs/testing/** - Testing strategy and test maps
5. **docs/dashboards/** - Monitoring and quality dashboards
6. **docs/runbooks/** - Operational procedures
7. **docs/archive/** - Historical documentation (not actively maintained)

## Contributing to Documentation

When adding or updating documentation:

1. **Keep canonical docs current** - Update authoritative references first
2. **Use clear titles** - Enable easy navigation and search
3. **Cross-reference** - Link related documents
4. **Archive obsolete docs** - Move completed session notes to `docs/archive/`
5. **Update this index** - Keep INDEX.md synchronized with new additions

## Feedback

Found a broken link or outdated information? Please:
1. Check the document's status at the top (if present)
2. Look for the document in `docs/archive/` if missing
3. Open an issue or submit a PR to fix it

For questions about documentation structure or to suggest improvements, see [CONTRIBUTING.md](../CONTRIBUTING.md).
