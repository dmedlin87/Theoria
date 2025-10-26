# Documentation Inventory & Freshness Audit

> **Last Updated:** 2025-10-26  
> **Maintainers:** Documentation working group

This inventory reflects the streamlined documentation set after the October 26 archiving pass. Active references stay lightweight and task-focused; superseded material has been moved to dated archive folders with an explicit banner.

## Canonical Entry Points

| Path | Purpose | Status |
| --- | --- | --- |
| `README.md` | Project overview, setup, and documentation policy | Authoritative |
| `START_HERE.md` | PowerShell launcher and local bootstrap | Authoritative |
| `CONTRIBUTING.md` | Contribution workflow, tooling, and review checklist | Authoritative |
| `SECURITY.md` | Disclosure process and security posture | Authoritative |
| `THREATMODEL.md` | Active threat model | Authoritative |
| `codebase_stabilization_plan.md` | Stability and resilience workstream tracker | Archived |
| `Repo-Health.md` | Repository KPIs and follow-up actions | Authoritative |

## Active `docs/` References

- **Architecture:** [`architecture.md`](architecture.md), [`architecture_review.md`](architecture_review.md)
- **API & Agents:** [`API.md`](API.md), [`theoria_instruction_prompt.md`](theoria_instruction_prompt.md), [`AGENT_CONFINEMENT.md`](AGENT_CONFINEMENT.md)
- **Quality:** [`testing.md`](testing.md), [`tests/utils/query_profiler.py`](../tests/utils/query_profiler.py)
- **Navigation:** [`INDEX.md`](INDEX.md), [`document_inventory.md`](document_inventory.md)

## Archive Layout

- **2025-10-26 Core Archive:** [`docs/archive/2025-10-26_core/`](archive/2025-10-26_core/) — superseded specifications, roadmaps, and feature briefs. Each file begins with an archive banner noting the date.
- **Historical Collections:** Existing dated and topic-specific folders remain under [`docs/archive/`](archive/).

## Archived Plans

- [codebase_stabilization_plan.md](archive/2025-10-26_core/codebase_stabilization_plan.md) (archived 2025-10-26)

When reviving archived material, remove the banner, move the document back under `docs/`, and update both this inventory and the `Documentation Map` table in the root `README`.

## Maintenance Checklist

1. Confirm new documents are essential before placing them at the root of `docs/`.
2. If a document becomes stale or is replaced, follow the [Documentation Archival Workflow](../README.md#documentation-archival-workflow).
3. Run a quick `rg --files docs` scan monthly to ensure no orphaned files bypass the inventory.
4. Update `Last Updated` metadata in this file whenever the structure changes.
