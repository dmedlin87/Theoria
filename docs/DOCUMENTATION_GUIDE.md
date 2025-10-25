# Documentation Guide

> Quick reference for navigating and maintaining Theoria documentation

## Finding Documentation

### Start Here
- **📚 [docs/INDEX.md](INDEX.md)** – Navigation across the updated taxonomy
- **🏠 [README.md](../README.md)** – Product overview and capability tour
- **🚀 [START_HERE.md](../START_HERE.md)** – Launcher scripts and troubleshooting

### By Persona

**New Contributors**
1. [CONTRIBUTING.md](../CONTRIBUTING.md) – Development workflow and tooling
2. [docs/BLUEPRINT.md](BLUEPRINT.md) – Architecture context before diving into code
3. [docs/testing/TEST_MAP.md](testing/TEST_MAP.md) – Quality gates and coverage expectations

**AI Agents & Research Assistants**
1. [QUICK_START_FOR_AGENTS.md](../QUICK_START_FOR_AGENTS.md) – Mission briefing and onboarding checklist
2. [AGENT_HANDOFF_COMPLETE.md](../AGENT_HANDOFF_COMPLETE.md) – Canonical artifact bundle
3. [docs/AGENT_AND_PROMPTING_GUIDE.md](AGENT_AND_PROMPTING_GUIDE.md) – Guardrails and reasoning frameworks

**Product & Program Leads**
1. [docs/ROADMAP.md](ROADMAP.md) – Milestones aligned to the Cognitive Scholar phases
2. [docs/status/FEATURE_INDEX.md](status/FEATURE_INDEX.md) – Review cadence for feature documentation
3. [docs/tasks/README.md](tasks/README.md) – Planning stubs and follow-up ledgers

**Platform & API Engineers**
1. [docs/API.md](API.md) – Endpoint reference and SDK notes
2. [docs/CLI.md](CLI.md) – Automation entry points
3. [docs/architecture.md](architecture.md) & [docs/adr/](adr/) – Dependency rules and decisions

**Operations & Reliability**
1. [docs/SERVICE_MANAGEMENT.md](SERVICE_MANAGEMENT.md) – Service orchestration
2. [docs/runbooks/](runbooks/) – Incident and escalation playbooks
3. [docs/dashboards/](dashboards/) – Observability and quality dashboards

## Documentation Structure

```
Theoria/
├── README.md                       # Product overview
├── START_HERE.md                   # Launcher & troubleshooting
├── QUICK_START_FOR_AGENTS.md       # Agent onboarding packet
├── AGENT_HANDOFF_COMPLETE.md       # Handoff artifact manifest
├── HANDOFF_NEXT_PHASE.md           # Cognitive Scholar roadmap
├── NEXT_STEPS.md                   # Active follow-up queue
├── CONTRIBUTING.md                 # Developer workflow
├── SECURITY.md / THREATMODEL.md    # Security posture
├── DEPLOYMENT.md                   # Deployment guide
│
└── docs/
    ├── INDEX.md                    # Navigation hub (topic-based)
    ├── DOCUMENTATION_GUIDE.md      # This guide
    ├── ROADMAP.md                  # Program milestones
    ├── BLUEPRINT.md                # Architecture blueprint
    ├── architecture.md             # Dependency guardrails
    ├── API.md / CLI.md / authentication.md
    ├── AGENT_AND_PROMPTING_GUIDE.md
    ├── CASE_BUILDER.md / DISCOVERY_FEATURE.md
    ├── reviews/                    # Architecture & safety reviews
    ├── status/                     # Feature index + bug ledgers
    ├── tasks/                      # Planning docs & checklists
    ├── runbooks/                   # Operational playbooks
    ├── dashboards/                 # Observability snapshots
    ├── testing/                    # Strategies, matrices, suites
    ├── security/                   # Scan outputs & governance
    ├── process/                    # Execution logs & retros
    ├── dev/                        # Environment notes
    ├── adr/                        # Architecture decision records
    └── archive/                    # Historical (not maintained)
        ├── README.md
        ├── 2025-10/
        ├── audits/
        ├── fixes/
        ├── planning/
        └── ui-sessions/
```

## Document Types

### Canonical References
**Status:** Always current and authoritative

- Root-level guides (README, START_HERE, QUICK_START_FOR_AGENTS, CONTRIBUTING, SECURITY, DEPLOYMENT, THREATMODEL)
- Core specs under `docs/` (API.md, CLI.md, BLUEPRINT.md, ROADMAP.md, AGENT_AND_PROMPTING_GUIDE.md, architecture.md)
- Governance directories (`docs/status/`, `docs/security/`, `docs/testing/`)
- Architecture Decision Records (`docs/adr/`)

**Maintenance:** Update immediately when behavior, process, or guardrail expectations change.

### Implementation Guides
**Status:** Living documentation

- docs/IMPLEMENTATION_GUIDE.md
- docs/ui_guidelines.md
- docs/typing-standards.md
- docs/debugging-guide.md
- docs/runbooks/
- docs/reviews/

**Maintenance:** Refresh as patterns evolve or after post-incident reviews.

### Historical Archives
**Status:** Point-in-time snapshots, not maintained

- docs/archive/2025-10/ – October 2025 session summaries
- docs/archive/fixes/ – Bug reports and one-off mitigations
- docs/archive/audits/ – Historical audit snapshots
- docs/archive/planning/ – Completed plans and agent task logs
- docs/archive/ui-sessions/ – UI refactoring notes

**Maintenance:** Only add new materials or README context; avoid editing existing records.

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

1. **Edit canonical docs directly** when behavior or guardrails change.
2. **Update `docs/INDEX.md` and `docs/status/FEATURE_INDEX.md`** when adding, renaming, or retiring major docs.
3. **Stage retros and worklogs in `docs/process/`** until the effort ships; archive once closed out.
4. **Maintain consistent naming** (“Theoria”) and taxonomy tags across directories.
5. **Cross-reference** related documents so newcomers can pivot between directories quickly.

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

After creating, update `docs/INDEX.md` and the relevant directory README (for example `docs/status/README.md`).

### Archiving Documents

```bash
# Session notes → archive/YYYY-MM/
# Bug reports → archive/fixes/
# Audits → archive/audits/
# Completed plans → archive/planning/
# UI refactoring → archive/ui-sessions/
```

Add context in the archive directory's README.md and surface the new link in `docs/INDEX.md` under **Historical context**.

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
| **AI Agents** | [QUICK_START_FOR_AGENTS.md](../QUICK_START_FOR_AGENTS.md), [docs/AGENT_AND_PROMPTING_GUIDE.md](AGENT_AND_PROMPTING_GUIDE.md) |
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
