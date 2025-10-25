# Documentation Index

> **Last Updated:** October 2025

This index provides a navigational overview of all Theoria documentation, organized by topic and audience.

## 📋 Table of Contents

- [Getting Started](#getting-started)
- [AI Agents & Cognitive Scholar](#ai-agents--cognitive-scholar)
- [Product & Program Management](#product--program-management)
- [Platform & Integrations](#platform--integrations)
- [Architecture & Engineering](#architecture--engineering)
- [Operations & Runbooks](#operations--runbooks)
- [Quality & Observability](#quality--observability)
- [Security & Risk](#security--risk)
- [Governance & Status](#governance--status)
- [Historical & Archives](#historical--archives)

---

## Getting Started

**Essentials for every newcomer:**

- [README.md](../README.md) – Product overview and capability tour
- [START_HERE.md](../START_HERE.md) – Launcher scripts and troubleshooting tips
- [docs/INDEX.md](INDEX.md) – Navigation hub for the documentation taxonomy
- [docs/DOCUMENTATION_GUIDE.md](DOCUMENTATION_GUIDE.md) – Maintenance policy and structure
- [CONTRIBUTING.md](../CONTRIBUTING.md) – Development workflow and expectations

## AI Agents & Cognitive Scholar

- [QUICK_START_FOR_AGENTS.md](../QUICK_START_FOR_AGENTS.md) – Orientation packet for incoming agents
- [AGENT_HANDOFF_COMPLETE.md](../AGENT_HANDOFF_COMPLETE.md) – Canonical artifact manifest
- [HANDOFF_NEXT_PHASE.md](../HANDOFF_NEXT_PHASE.md) – Phase-by-phase Cognitive Scholar roadmap
- [COGNITIVE_SCHOLAR_HANDOFF_NEW.md](../COGNITIVE_SCHOLAR_HANDOFF_NEW.md) – Domain decisions and context
- [IMPLEMENTATION_CONTEXT.md](../IMPLEMENTATION_CONTEXT.md) – Architecture constraints and integration guidance
- [docs/AGENT_AND_PROMPTING_GUIDE.md](AGENT_AND_PROMPTING_GUIDE.md) – Prompting guardrails and reasoning workflows
- [docs/AGENT_CONFINEMENT.md](AGENT_CONFINEMENT.md) – Safety framework for MCP agents
- [docs/AGENT_THINKING_ENHANCEMENT.md](AGENT_THINKING_ENHANCEMENT.md) – Reasoning improvements and evaluation
- [docs/mcp_integration_guide.md](mcp_integration_guide.md) – Model Context Protocol integration

## Product & Program Management

- [docs/ROADMAP.md](ROADMAP.md) – Cognitive Scholar milestones and checkpoints
- [NEXT_STEPS.md](../NEXT_STEPS.md) – Active delivery queue and follow-ups
- [docs/FUTURE_FEATURES_ROADMAP.md](FUTURE_FEATURES_ROADMAP.md) – Prioritized feature backlog
- [docs/tasks/README.md](tasks/README.md) – Task ledgers and planning stubs
- [docs/status/FEATURE_INDEX.md](status/FEATURE_INDEX.md) – Ownership and review cadence for feature docs
- [docs/DISCOVERY_FEATURE.md](DISCOVERY_FEATURE.md) & [docs/DISCOVERY_QUICK_START.md](DISCOVERY_QUICK_START.md) – Discovery Feed specification and walkthrough
- [docs/CASE_BUILDER.md](CASE_BUILDER.md) – Case Builder specification with links to archived iterations
- [docs/TREND_ANOMALY_DETECTOR_RESEARCH.md](TREND_ANOMALY_DETECTOR_RESEARCH.md) – Research blueprint for trend/anomaly maturity

## Platform & Integrations

- [docs/API.md](API.md) – FastAPI endpoints and SDK notes
- [docs/authentication.md](authentication.md) – Authentication configuration (API keys, JWT, anonymous)
- [docs/CLI.md](CLI.md) – Command-line automation reference
- [docs/Chunking.md](Chunking.md) & [docs/Frontmatter.md](Frontmatter.md) – Ingestion and parsing strategy
- [docs/OSIS.md](OSIS.md) – Scripture normalization rules
- [docs/theoria_instruction_prompt.md](theoria_instruction_prompt.md) – System prompt engineering for assistants
- [`theo/services/cli`](../theo/services/cli) – CLI source layout and packaging
- [docs/ARCHITECTURE_MIGRATION_EXAMPLE.md](ARCHITECTURE_MIGRATION_EXAMPLE.md) – Reference for migrating services into the new structure

## Architecture & Engineering

- [docs/BLUEPRINT.md](BLUEPRINT.md) – System architecture blueprint
- [docs/architecture.md](architecture.md) – Dependency boundaries and enforcement
- [docs/CODEBASE_REVIEW.md](CODEBASE_REVIEW.md) – Architectural analysis and patterns
- [docs/ARCHITECTURE_IMPROVEMENTS.md](ARCHITECTURE_IMPROVEMENTS.md) & [docs/refactor_modularity_plan.md](refactor_modularity_plan.md) – Platform modernization tracks
- [docs/Modularity-Plan.md](Modularity-Plan.md) – Module boundaries and ownership
- [docs/reviews/](reviews/) – Architecture, safety, and reasoning reviews
- [docs/adr/](adr/) – Architecture Decision Records
- [docs/reranker_mvp.md](reranker_mvp.md) & [docs/CONTRADICTION_DETECTION.md](CONTRADICTION_DETECTION.md) – Specialized engineering initiatives

## Operations & Runbooks

- [DEPLOYMENT.md](../DEPLOYMENT.md) – Deployment process, signing, and environments
- [docs/SERVICE_MANAGEMENT.md](SERVICE_MANAGEMENT.md) – Service orchestration and operations
- [docs/runbooks/](runbooks/) – Incident response and operational playbooks
- [docs/process/](process/) – Execution logs, retrospectives, and process notes
- [scripts/RUN_SCRIPTS_README.md](../scripts/RUN_SCRIPTS_README.md) – Automation scripts and task helpers
- [start-theoria.ps1](../start-theoria.ps1) & [scripts/dev.ps1](../scripts/dev.ps1) / [scripts/run.sh](../scripts/run.sh) – Local orchestration
- [docs/production_readiness_gaps.md](production_readiness_gaps.md) – Pre-production checklist
- [.github/workflows/](../.github/workflows/) – CI/CD pipelines

## Quality & Observability

- [docs/testing/TEST_MAP.md](testing/TEST_MAP.md) – Comprehensive testing matrix
- [docs/testing/](testing/) – Test strategies, schemas, and suite overviews
- [docs/ui-quality-gates.md](ui-quality-gates.md) – UI acceptance criteria
- [docs/dashboards/](dashboards/) – Observability and quality dashboards
- [dashboard/coverage-dashboard.md](../dashboard/coverage-dashboard.md) – Coverage reporting
- [metrics/README.md](../metrics/README.md) – Metrics collection and alerting
- [docs/performance.md](performance.md) & [docs/lighthouse-ci.md](lighthouse-ci.md) – Performance baselines and thresholds
- [docs/test_failure_analysis_2025_10_16.md](test_failure_analysis_2025_10_16.md) – Postmortem for regression fixes

## Security & Risk

- [SECURITY.md](../SECURITY.md) – Security policy and disclosure process
- [THREATMODEL.md](../THREATMODEL.md) – Threat modeling reference
- [docs/security/](security/) – Secret scanning baselines and security automation
- [docs/redteam.md](redteam.md) – Red-team findings and mitigations
- [docs/AGENT_CONFINEMENT.md](AGENT_CONFINEMENT.md) – Agent isolation controls
- [docs/Repo-Health.md](Repo-Health.md) – Repository health analysis
- [docs/audit_mode_spec.md](audit_mode_spec.md) – Audit-mode requirements

## Governance & Status

- [docs/document_inventory.md](document_inventory.md) – Inventory and freshness audit
- [docs/status/README.md](status/README.md) – Governance workflow for feature docs and bug ledgers
- [docs/status/KnownBugs.md](status/KnownBugs.md) – Active bug ledger
- [docs/status/KnownBugs_archive.md](status/KnownBugs_archive.md) – Historical bug ledger
- [docs/reviews/ai_reasoning_review.md](reviews/ai_reasoning_review.md) & [docs/reviews/api_security_review.md](reviews/api_security_review.md) – Review artifacts with required follow-ups

## Historical & Archives

**Historical documents preserved for reference:**

- [docs/archive/README.md](archive/README.md) – Archive overview and retention policy
- [docs/archive/2025-10/](archive/2025-10/) – October 2025 session summaries
- [docs/archive/audits/](archive/audits/) – Historical audits
- [docs/archive/fixes/](archive/fixes/) – Resolved bug fix reports
- [docs/archive/planning/](archive/planning/) – Completed planning documents and agent task breakdowns
- [docs/archive/ui-sessions/](archive/ui-sessions/) – UI/UX refactoring session notes

---

## Document Organization Principles

1. **Root-level onboarding** – Product overview, launch instructions, and agent handoffs
2. **docs/** – Active specifications, guides, and reference material organized by directory
3. **docs/adr/** – Architecture Decision Records (permanent commitments)
4. **docs/status/** – Governance indexes for feature docs and bug ledgers
5. **docs/runbooks/** & **docs/process/** – Operational playbooks and retrospectives
6. **docs/testing/** & **docs/dashboards/** – Quality strategies and observability assets
7. **docs/archive/** – Historical documentation (not actively maintained)

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
