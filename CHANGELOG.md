# Changelog

[⬅️ Back to the README](README.md)

> Generated from `git log --date=short --pretty="%cs %h %s"` on the current mainline. Update this file whenever you land noteworthy fixes, features, or documentation reorganizations.

## Recent History
- 2025-10-25 · 8f14441 · Add slow test baseline tooling (#1200)
- 2025-10-25 · 7e2f2cc · Add dependency graph generation tooling (#1199)
- 2025-10-25 · 59d2fc0 · Refactor AI router tests to inject sleep stubs (#1198)
- 2025-10-25 · cfd98ff · test: track slowest pytest durations (#1197)
- 2025-10-25 · 63b64e7 · Organize debug utilities and transcripts (#1196)

## How to Extend
1. After completing a change, run `git log -n 5 --date=short --pretty="%cs %h %s"` (or similar) to collect the latest entries.
2. Append the new summary at the top of the list with the same `date · short-hash · subject` format.
3. When documenting multi-file reorganizations, include direct links to the affected docs or directories for easy navigation.

Need a broader view? Use `git log --since="2025-10-01" --stat` or tooling in `scripts/` to generate deeper analytics before condensing here.
