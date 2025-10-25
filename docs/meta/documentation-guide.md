# Documentation Guide

> Quick reference for navigating and maintaining Theoria documentation

## Finding Documentation

### Start Here
- **📚 [Documentation Index](index.md)** - Complete documentation index organized by topic
- **🏠 [README.md](../README.md)** - Project overview and quick start
- **🤝 [CONTRIBUTING.md](../CONTRIBUTING.md)** - How to contribute

### By Role

**New Users:**
1. [README.md](../README.md) - What is Theoria?
2. [START_HERE.md](../START_HERE.md) - Launch the application
3. [Discovery Quick Start](../features/discovery/quick-start.md) - Try the Discovery Feed

**Contributors:**
1. [CONTRIBUTING.md](../CONTRIBUTING.md) - Setup and workflow
2. [UI Guidelines](../development/ui-guidelines.md) - UI development standards
3. [Typing Standards](../development/typing-standards.md) - Type system conventions
4. [Testing Map](../testing/TEST_MAP.md) - Testing strategy

**API Developers:**
1. [API Reference](../development/api-reference.md) - API reference
2. [Authentication](../development/authentication.md) - Auth setup
3. [Clean Architecture](../architecture/clean-architecture.md) - System architecture

**DevOps:**
1. [Deployment Overview](../operations/deployment-overview.md) - Deployment guide
2. [Service Management](../operations/service-management.md) - Service orchestration
3. [SECURITY.md](../SECURITY.md) - Security policy

## Documentation Structure

```
Theoria/
├── README.md                   # Entry point
├── CONTRIBUTING.md             # Developer guide
├── SECURITY.md                 # Security policy
├── START_HERE.md               # Quick start
├── THREATMODEL.md              # Threat model
├── DOCUMENTATION_CLEANUP_SUMMARY.md  # Cleanup report
│
└── docs/
    ├── agents/                 # Agent architecture & prompting
    ├── architecture/           # System design and reviews
    ├── development/            # API, CLI, data processing guides
    ├── features/               # Feature specifications by product area
    ├── operations/             # Deployment, telemetry, reliability
    ├── testing/                # Testing strategy and reports
    ├── security/               # Security audits and hardening
    ├── meta/                   # Indexes and documentation standards
    ├── tasks/                  # Active task handoffs
    ├── status/                 # Status reports and triage plans
    ├── runbooks/               # Operational procedures
    ├── dashboards/             # Monitoring snapshots
    └── archive/                # Historical docs (not actively maintained)
```

## Document Types

### Canonical References
**Status:** Always current and authoritative

- Root-level guides (README, CONTRIBUTING, SECURITY, etc.)
- docs/agents/prompting-guide.md, docs/development/api-reference.md
- Feature specifications (e.g., `docs/features/discovery/overview.md`)
- Architecture Decision Records (`docs/adr/`)
- Testing strategy (`docs/testing/TEST_MAP.md`)

**Maintenance:** Update immediately when behavior changes

### Implementation Guides
**Status:** Living documentation

- docs/agents/implementation-guide.md
- docs/development/ui-guidelines.md
- docs/development/typing-standards.md
- docs/development/debugging-guide.md

**Maintenance:** Update as patterns evolve

### Historical Archives
**Status:** Point-in-time snapshots, not maintained

- docs/archive/2025-10/ - Session summaries
- docs/archive/fixes/ - Bug reports
- docs/archive/audits/ - Audit snapshots
- docs/archive/planning/ - Completed plans

**Maintenance:** Add new archives, rarely modify existing

## When to Archive

Move documents to `docs/archive/` when they are:

1. **Session summaries** - Implementation logs from specific work sessions
2. **Point-in-time reports** - Bug fixes, audits, reviews that are complete
3. **Superseded specifications** - Older versions replaced by new specs
4. **Completed plans** - Task breakdowns and action items that are done
5. **Refactoring notes** - Session notes from completed refactoring work

**Keep active** if the document:
- Describes current system behavior
- Is referenced by users or contributors
- Contains operational procedures
- Defines active standards or patterns

## Updating Documentation

### Making Changes

1. **Edit canonical docs directly** for behavior changes
2. **Update the index** when adding/removing major docs
3. **Archive completed session notes** after merging features
4. **Update branding** consistently (use "Theoria", not "Theo Engine")
5. **Cross-reference** related documents with links

### Adding New Documentation

```bash
# Feature documentation
docs/features/<feature>/<topic>.md

# Architecture decisions
docs/adr/NNNN-decision-title.md

# Operational runbooks
docs/runbooks/issue_name_runbook.md

# Testing guides
docs/testing/test_type_guide.md
```

After creating, update `docs/meta/index.md` in the appropriate section.

### Archiving Documents

```bash
# Session notes → archive/YYYY-MM/
# Bug reports → archive/fixes/
# Audits → archive/audits/
# Completed plans → archive/planning/
# UI refactoring → archive/ui-sessions/
```

Add context in the archive directory's README.md.

## Documentation Standards

### File Naming
- Use `SCREAMING_SNAKE_CASE.md` for major guides when specified by stakeholders
- Prefer `kebab-case.md` for ADRs and focused topics
- Use descriptive names that indicate content

### Structure
```markdown
# Title

> **Status:** [Active|Planned|Archived]
> **Last Updated:** [Date]

## Overview

Brief description...

## Sections...
```

### Links
- Keep relative links accurate after moving files
- Prefer linking to canonical docs in the new directory layout
