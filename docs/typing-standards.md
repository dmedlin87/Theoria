# Typing standards rollout communication

## Why this matters
We are expanding mypy coverage to catch type drift in the API layer and to remove stale
`# type: ignore` comments. The phased roadmap in [ADR 0002](adr/0002-strict-typing-roadmap.md)
explains which modules will move to strict typing first and how `warn-unused-ignores` will
become mandatory once the groundwork is complete.

## Expectations for new code
- Prefer explicit type annotations on public functions, dataclasses, and Pydantic models.
- New `# type: ignore` comments must include a specific error code and a TODO or issue link.
  Omitting either will cause CI to fail once `warn-unused-ignores` is enabled.
- If you touch a module listed in Phase 1 of the roadmap, treat missing annotations or
  broad ignores as bugs to be fixed immediately.
- Run `mypy --config-file mypy.ini` locally before opening a PR. If you are validating the
  roadmap work, also run `mypy --config-file mypy.ini --warn-unused-ignores` to ensure we
  are ready for the CI toggle.

## Coordinating the rollout
- Track remaining ignores and strictness gaps in a shared issue or spreadsheet, grouped by
  module owners. Update the tracker as you remove ignores so we can measure progress toward
  the Phase 1 and Phase 2 milestones.
- When Phase 1 is complete, a repo admin can flip the `ENABLE_WARN_UNUSED_IGNORES`
  repository variable to `true`. The CI workflow will then execute the stricter mypy step
  on every PR without further code changes.
- Share weekly progress in standups so the team knows which modules are ready for strict
  enforcement and where help is needed.
- Document any third-party typing gaps (e.g., missing stubs) in follow-up issues so we can
  decide whether to vendor custom stubs or contribute upstream.

## Getting help
If you run into typing edge cases or need guidance on removing `Any` usage, reach out in
#theo-engineering. Collect tricky examples in a shared gist or notebook so we can extend
the contributor documentation over time.
