> **Archived on 2025-10-26**

# Documentation Guide

> Quick reference for navigating and maintaining Theoria documentation

## Finding Documentation

### Start Here
- **📚 [docs/INDEX.md](INDEX.md)** - Complete documentation index organized by topic
- **🏠 [README.md](../README.md)** - Project overview and quick start
- **🤝 [CONTRIBUTING.md](../CONTRIBUTING.md)** - How to contribute

### By Role

**New Users:**
1. [README.md](../README.md) - What is Theoria?
2. [START_HERE.md](../START_HERE.md) - Launch the application
3. [docs/DISCOVERY_QUICK_START.md](DISCOVERY_QUICK_START.md) - Try the Discovery Feed

**Contributors:**
1. [CONTRIBUTING.md](../CONTRIBUTING.md) - Setup and workflow
2. [docs/ui_guidelines.md](ui_guidelines.md) - UI development standards
3. [docs/typing-standards.md](typing-standards.md) - Type system conventions
4. [docs/testing/TEST_MAP.md](testing/TEST_MAP.md) - Testing strategy

**API Developers:**
1. [docs/API.md](API.md) - API reference
2. [docs/authentication.md](authentication.md) - Auth setup
3. [docs/BLUEPRINT.md](BLUEPRINT.md) - System architecture

**DevOps:**
1. [DEPLOYMENT.md](../DEPLOYMENT.md) - Deployment guide
2. [docs/SERVICE_MANAGEMENT.md](SERVICE_MANAGEMENT.md) - Service orchestration
3. [SECURITY.md](../SECURITY.md) - Security policy

## Documentation Structure

```
Theoria/
├── README.md                   # Entry point
├── CONTRIBUTING.md             # Developer guide
├── SECURITY.md                 # Security policy
├── DEPLOYMENT.md               # Deployment guide
├── START_HERE.md               # Quick start
├── THREATMODEL.md              # Threat model
├── DOCUMENTATION_CLEANUP_SUMMARY.md  # Cleanup report
│
└── docs/
    ├── INDEX.md                # Master index (START HERE)
    ├── DOCUMENTATION_GUIDE.md  # This file
    ├── CASE_BUILDER.md         # Case Builder spec
    │
    ├── [Feature Docs]
    │   ├── DISCOVERY_FEATURE.md
    │   ├── DISCOVERY_QUICK_START.md
    │   └── FUTURE_FEATURES_ROADMAP.md
    │
    ├── [API & Development]
    │   ├── API.md
    │   ├── CLI.md
    │   ├── authentication.md
    │   ├── Chunking.md
    │   └── ...
    │
    ├── [Architecture]
    │   ├── BLUEPRINT.md
    │   ├── CODEBASE_REVIEW.md
    │   ├── AGENT_CONFINEMENT.md
    │   └── adr/                # Architecture Decision Records
    │
    ├── [Operations]
    │   ├── SERVICE_MANAGEMENT.md
    │   ├── performance.md
    │   ├── debugging-guide.md
    │   └── runbooks/
    │
    ├── [Testing]
    │   ├── testing/TEST_MAP.md
    │   ├── ui-quality-gates.md
    │   └── ui_guidelines.md
    │
    └── archive/                # Historical docs (not actively maintained)
        ├── README.md           # Archive policy
        ├── 2025-10/           # October 2025 sessions
        ├── fixes/             # Bug fix reports
        ├── audits/            # Audit snapshots
        ├── planning/          # Completed plans
        └── ui-sessions/       # UI refactoring notes
```

## Document Types

### Canonical References
**Status:** Always current and authoritative

- Root-level guides (README, CONTRIBUTING, SECURITY, etc.)
- docs/API.md, docs/CLI.md, docs/BLUEPRINT.md
- Feature specifications (DISCOVERY_FEATURE.md, CASE_BUILDER.md)
- Architecture Decision Records (docs/adr/)
- Testing strategy (docs/testing/TEST_MAP.md)

**Maintenance:** Update immediately when behavior changes

### Implementation Guides
**Status:** Living documentation

- docs/IMPLEMENTATION_GUIDE.md
- docs/ui_guidelines.md
- docs/typing-standards.md
- docs/debugging-guide.md

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
2. **Update the INDEX.md** when adding/removing major docs
3. **Archive completed session notes** after merging features
4. **Update branding** consistently (use "Theoria", not "Theo Engine")
5. **Cross-reference** related documents with links

### Adding New Documentation

```bash
# Feature documentation
docs/FEATURE_NAME.md

# Architecture decisions
docs/adr/NNNN-decision-title.md

# Operational runbooks
docs/runbooks/issue_name_runbook.md

# Testing guides
docs/testing/test_type_guide.md
```

After creating, update `docs/INDEX.md` in the appropriate section.

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
- Use `SCREAMING_SNAKE_CASE.md` for major guides
- Use `kebab-case.md` for ADRs and specific topics
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
- Use relative links: `[text](../path/to/doc.md)`
- Link to specific sections: `[text](doc.md#section)`
- Keep links working after moves (update or redirect)

### Code Examples
- Include language identifiers: ```python, ```typescript
- Show complete, runnable examples
- Explain non-obvious behavior

## Common Tasks

### I need to...

**Find API documentation**  
→ [docs/API.md](API.md)

**Understand the architecture**  
→ [docs/BLUEPRINT.md](BLUEPRINT.md) and [docs/adr/](adr/)

**Learn about a feature**  
→ Check [docs/INDEX.md](INDEX.md) Features section

**Review historical decisions**  
→ Browse [docs/archive/](archive/) with context from archive READMEs

**Add a new feature spec**  
→ Create `docs/FEATURE_NAME.md`, update [docs/INDEX.md](INDEX.md)

**Archive completed work**  
→ Move to appropriate `docs/archive/` subdirectory, update archive README

**Fix outdated docs**  
→ Edit canonical source directly, don't create duplicates

**Report doc issues**  
→ Open issue or submit PR with fixes

## Quick Links

| Topic | Link |
|-------|------|
| **Navigation** | [docs/INDEX.md](INDEX.md) |
| **Getting Started** | [README.md](../README.md), [START_HERE.md](../START_HERE.md) |
| **API Reference** | [docs/API.md](API.md) |
| **Architecture** | [docs/BLUEPRINT.md](BLUEPRINT.md) |
| **Security** | [SECURITY.md](../SECURITY.md), [THREATMODEL.md](../THREATMODEL.md) |
| **Contributing** | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| **Testing** | [docs/testing/TEST_MAP.md](testing/TEST_MAP.md) |
| **Archive** | [docs/archive/README.md](archive/README.md) |

## Maintenance Schedule

- **Weekly:** Check for broken links in active docs
- **Monthly:** Review recent changes for docs that need updates
- **Quarterly:** Archive completed session notes and reports
- **Yearly:** Review entire documentation structure for relevance

## Questions?

- Check [docs/INDEX.md](INDEX.md) for comprehensive navigation
- Review [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines
- Open an issue for documentation problems or suggestions

---

**Last Updated:** October 2025  
**Maintained By:** Project contributors  
**Source:** c:\Users\dmedl\Projects\Theoria\docs\DOCUMENTATION_GUIDE.md
