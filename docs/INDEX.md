# Documentation Index

> **Last Updated:** October 2025

This index provides a navigational overview of all Theoria documentation, organized by topic and audience.

## 📋 Table of Contents

- [Getting Started](#getting-started)
- [Development](#development)
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
- [docs/IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) - AI scaffolding and implementation patterns

## Development

### API Documentation
- [docs/API.md](API.md) - FastAPI endpoints and authentication
- [docs/authentication.md](authentication.md) - Auth configuration (API keys, JWT, anonymous)
- [docs/CLI.md](CLI.md) - Command-line interface reference

### Data Processing
- [docs/Chunking.md](Chunking.md) - Document chunking strategies
- [docs/Frontmatter.md](Frontmatter.md) - Metadata extraction from frontmatter
- [docs/OSIS.md](OSIS.md) - Scripture reference normalization

### UI Development
- [docs/ui_guidelines.md](ui_guidelines.md) - Design system and component patterns
- [docs/UI_NAVIGATION_LOADING_IMPROVEMENTS.md](UI_NAVIGATION_LOADING_IMPROVEMENTS.md) - Navigation and loading best practices
- [theo/services/web/tests/README.md](../theo/services/web/tests/README.md) - Frontend testing guide
- [theo/services/web/public/keyboard-shortcuts.md](../theo/services/web/public/keyboard-shortcuts.md) - Keyboard shortcuts reference

### Code Quality
- [docs/typing-standards.md](typing-standards.md) - TypeScript and Python typing conventions
- [docs/debugging-guide.md](debugging-guide.md) - Debugging strategies and tools
- [mypy.ini](../mypy.ini), [mypy_mcp.ini](../mypy_mcp.ini) - Type checking configuration

## Features

### Discovery Feed
- [docs/DISCOVERY_FEATURE.md](DISCOVERY_FEATURE.md) - Complete feature specification
- [docs/DISCOVERY_QUICK_START.md](DISCOVERY_QUICK_START.md) - Quick start guide for discoveries
- **Status:** Frontend complete, backend planned

### Case Builder
- [docs/CASE_BUILDER.md](CASE_BUILDER.md) - Consolidated specification and roadmap
- [docs/archive/planning/case-builder/](archive/planning/case-builder/) - Historical versions (v1-v4)
- **Status:** Planned (v4 specification ready)

### Future Features
- [docs/FUTURE_FEATURES_ROADMAP.md](FUTURE_FEATURES_ROADMAP.md) - 25 planned features with priority matrix
- [docs/more_features.md](more_features.md) - Additional feature ideas

### Agent & MCP Integration
- [docs/mcp_integration_guide.md](mcp_integration_guide.md) - Model Context Protocol integration
- [docs/AGENT_CONFINEMENT.md](AGENT_CONFINEMENT.md) - Security framework for AI agents
- [docs/AGENT_THINKING_ENHANCEMENT.md](AGENT_THINKING_ENHANCEMENT.md) - Agent reasoning improvements
- [docs/theoria_instruction_prompt.md](theoria_instruction_prompt.md) - System prompt engineering
- [docs/adr/0001-expose-theoria-via-mcp.md](adr/0001-expose-theoria-via-mcp.md) - ADR: MCP exposure decision
- [docs/adr/0001-mcp-tools-and-apps-sdk.md](adr/0001-mcp-tools-and-apps-sdk.md) - ADR: MCP tools and SDK

## Architecture

### System Design
- [docs/BLUEPRINT.md](BLUEPRINT.md) - Complete system architecture and build spec
- [docs/CODEBASE_REVIEW.md](CODEBASE_REVIEW.md) - Architectural analysis and patterns
- [docs/adr/0001-hexagonal-architecture.md](adr/0001-hexagonal-architecture.md) - ADR: Hexagonal/ports-and-adapters pattern
- [docs/Modularity-Plan.md](Modularity-Plan.md) - Module boundaries and organization
- [docs/refactor_modularity_plan.md](refactor_modularity_plan.md) - Modularization strategy

### Technical Specifications
- [docs/performance.md](performance.md) - Performance benchmarks and optimization
- [docs/lighthouse-ci.md](lighthouse-ci.md) - Lighthouse CI integration and thresholds
- [docs/SERVICE_MANAGEMENT.md](SERVICE_MANAGEMENT.md) - Service orchestration and management
- [docs/telemetry.md](telemetry.md) - OpenTelemetry instrumentation
- [docs/reranker_mvp.md](reranker_mvp.md) - Reranking implementation

### Data Schemas
- [docs/case_builder.schema.json](case_builder.schema.json) - Case Builder JSON schema
- [fixtures/](../fixtures/) - Test fixtures and sample data

## Operations

### Deployment
- [DEPLOYMENT.md](../DEPLOYMENT.md) - Container builds and signing
- [.github/workflows/](../.github/workflows/) - CI/CD workflows
- [docs/production_readiness_gaps.md](production_readiness_gaps.md) - Pre-production checklist

### Service Management
- [start-theoria.ps1](../start-theoria.ps1) - Service launcher script
- [scripts/RUN_SCRIPTS_README.md](../scripts/RUN_SCRIPTS_README.md) - Orchestrator scripts
- [metrics/README.md](../metrics/README.md) - Prometheus metrics
- [docs/runbooks/performance_discrepancy_runbook.md](runbooks/performance_discrepancy_runbook.md) - Performance troubleshooting

### Monitoring & Dashboards
- [dashboard/coverage-dashboard.md](../dashboard/coverage-dashboard.md) - Test coverage dashboard
- [docs/dashboards/ui-quality-dashboard.md](dashboards/ui-quality-dashboard.md) - UI quality metrics
- [.lighthouseci/baseline/README.md](../.lighthouseci/baseline/README.md) - Lighthouse baseline thresholds

## Security

### Policies & Threat Model
- [SECURITY.md](../SECURITY.md) - Security policy and disclosure process
- [THREATMODEL.md](../THREATMODEL.md) - Comprehensive threat model
- [docs/AGENT_CONFINEMENT.md](AGENT_CONFINEMENT.md) - MCP agent security framework
- [docs/redteam.md](redteam.md) - Red team findings and mitigations

### Data & Repository Health
- [docs/Repo-Health.md](Repo-Health.md) - Repository health analysis
- [data/seeds/](../data/seeds/) - Seed data for testing

## Testing

### Testing Strategy
- [docs/testing/TEST_MAP.md](testing/TEST_MAP.md) - Comprehensive test map
- [docs/ui-quality-gates.md](ui-quality-gates.md) - UI quality gate criteria
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

- [docs/archive/README.md](archive/README.md) - Archive overview and retention policy
- [docs/archive/2025-10/](archive/2025-10/) - October 2025 session summaries
- [docs/archive/fixes/](archive/fixes/) - Resolved bug fix reports
- [docs/archive/audits/](archive/audits/) - Historical audit snapshots
- [docs/archive/planning/](archive/planning/) - Completed planning documents
- [docs/archive/ui-sessions/](archive/ui-sessions/) - UI/UX refactoring session notes

---

## Document Organization Principles

1. **Root-level docs** - User-facing guides (README, CONTRIBUTING, SECURITY, etc.)
2. **docs/** - Technical documentation, specifications, and guides
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
