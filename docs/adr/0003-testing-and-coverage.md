# ADR 0003: Enforce Coverage and Architecture Tests

- Status: Accepted
- Date: 2024-05-01

## Context

Refactors risk regressions without visibility. Existing pytest runs lacked coverage enforcement and no tests guarded architectural layering.

## Decision

- Add architecture-focused pytest suite that parses imports to detect forbidden dependencies across domain/application/adapters.
- Configure pytest to require ≥80% overall coverage and ≥90% for critical core packages.
- Install `pytest-cov` and integrate coverage reports into CI pipelines.

## Consequences

- CI fails fast when new code violates layering or reduces test coverage.
- Developers must extend or adjust tests when moving code between modules.
- Provides quantifiable metrics for release readiness and Scorecard checks.
