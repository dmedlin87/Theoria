> **Archived on 2025-10-26**

# Codebase Stabilization Plan

## Validated Context
- The `theo/infrastructure/api/app` package already spans adapters, analytics, ingest, research, transcripts, workers, and other feature slices, which makes the surface area difficult to keep in mind during day-to-day development.
- The pytest harness centralises extensive plugin registration, coverage shims, and database bootstrapping logic in `tests/conftest.py`, so even small changes can have wide-ranging side effects.
- Optional dependency groups in `pyproject.toml` pin security-sensitive libraries such as Celery, cryptography, SQLAlchemy, and PyJWT to exact versions, limiting the ability to pick up security fixes or compatible performance improvements.

## Immediate Priorities
1. **Stabilise the regression suite.** Run `pytest --maxfail=1 --disable-warnings` locally to confirm the current baseline, and capture flaky modules. Follow up with targeted runs for the heaviest groups (for example `pytest tests/api` and `pytest tests/ingest`) so breakages can be triaged without the full test matrix.
2. **Decouple heavyweight fixtures.** Extract external-service bootstrapping (containers, pgvector, etc.) from `tests/conftest.py` into feature-specific fixtures so that fast-running unit suites do not need to import infrastructure helpers.
3. **Document environment prerequisites.** Capture the Docker services, background workers, and environment variables required for the slow-path tests in `docs/testing.md` to reduce contributor onboarding friction.

## Dependency Hardening
- Convert `==` pins in `pyproject.toml` to compatible release ranges (for example `celery>=5.5.3,<6`) so automated tooling can deliver patch updates.
- Add a security scanning gate (e.g. `pip-audit` or `safety`) to CI and schedule a weekly check to ensure critical CVEs are surfaced immediately.
- Split truly optional ML packages into a dedicated extra so API-only deployments do not need to resolve heavyweight scientific wheels.

## Architectural Guardrails
- Expand `importlinter.ini` with explicit boundaries between `theo.domain`, `theo.application`, and `theo.services.api` feature folders to prevent accidental cross-layer imports.
- Introduce an internal ADR describing how modules inside `theo/infrastructure/api/app` should be grouped (core, interfaces, infrastructure, feature slices) and migrate modules incrementally to the agreed structure.
- Track N+1 query remediation by adding SQLAlchemy profiler hooks to the ingest and ranking pipelines while bulk update helpers are introduced.

## Success Criteria
- Consistently green test runs in CI with no untriaged flaky markers.
- Automated dependency scanning with zero outstanding high or critical alerts.
- Import-linter passes that enforce the chosen layering rules alongside a reduced number of shared, catch-all modules in the API package.
