# Known Bugs Ledger

Single source of truth for live issues. Update this table whenever a bug is opened, in progress, or resolved.

| ID | Title | Severity | Status | Owner | First Noted | Last Updated | Impacted Docs | Resolution Link |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _None_ | | | | | | | | |

## Workflow

1. **Open bug** → add a new row with `Status = Open` and reference any affected docs in `Impacted Docs`.
2. **Fix in progress** → change `Status` to `In Progress`, set `Owner`, and link the active branch/PR.
3. **Resolved** → update `Status` to `Resolved`, add PR/commit link, and ensure impacted docs remove or annotate the issue.
4. **Archive** → move resolved entries older than 60 days to `docs/status/KnownBugs_archive.md`.

Always ensure feature docs reference bugs by ID in their `Known Limitations & Bugs` sections.
