# Documentation & Bug Governance

This folder contains the living indexes that keep feature docs and bug records in sync.

- `FEATURE_INDEX.md` — authoritative map of feature documentation, ownership, review cadence, and status.
- `KnownBugs.md` — live ledger of open and in-progress bugs, referenced by feature docs.
- `KnownBugs_archive.md` — long-term storage for resolved bugs older than 60 days.

## Workflow Reminders

1. **When shipping features** update the relevant entry in `FEATURE_INDEX.md` with a new `Last Reviewed` date.
2. **When discovering bugs** log them in `KnownBugs.md` and link affected docs. Close entries only after code + docs are updated.
3. **PR checklist** (see `.github/PULL_REQUEST_TEMPLATE.md`) requires explicit confirmation that documentation and bug ledgers are current.
4. **Weekly rotation** scans for entries whose `Last Reviewed` date is older than 30 days, ensuring docs never drift.

CI enhancements should validate that:
- Modified docs listed in `FEATURE_INDEX.md` bump their `Last Reviewed` dates.
- Resolved bugs in code diffs include matching ledger updates.
- `scripts/check_docs_governance.py` passes in CI (see usage in `RUN_SCRIPTS_README.md`).
