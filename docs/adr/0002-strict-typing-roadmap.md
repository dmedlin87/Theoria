# ADR 0002: Phased roadmap for strict typing and warning on unused ignores

## Status
Accepted

## Context
Mypy is already configured for targeted strictness in parts of the API layer, but the
codebase still relies on broad `# type: ignore` usage and modules that operate with
implicit `Any` types. Running mypy with `--warn-unused-ignores` today produces a large
number of errors and exposes drift between modules that have strict checks enabled and
those that do not. We need a staged approach that expands strict typing coverage while
bringing the ignore usage under control so that enabling `warn-unused-ignores` in CI does
not break day-to-day development.

## Decision
We will execute the strict typing rollout in three phases. Each phase has an explicit
module scope, deliverables for typing coverage, and expectations for handling existing or
new `# type: ignore` comments.

### Phase 0 – Foundation and tooling support (in flight)
- Audit the current mypy configuration (`mypy.ini` and `pyproject.toml`) and consolidate on
  a single source of truth for shared defaults (e.g., `ignore_missing_imports`,
  `warn_unused_configs`).
- Inventory the existing `# type: ignore` usage across `theo/services/api/app` and produce
  a shared spreadsheet or issue tracker noting whether each ignore should be removed,
  replaced with a targeted error code, or temporarily grandfathered.
- Fix import-time blockers that prevent strict mode from being applied (e.g., missing
  pydantic/SQLAlchemy plugins, missing stub packages for PyYAML, and `Any` inheritance on
  database models).
- Update CI so that a `--warn-unused-ignores` run can be toggled on without further code
  changes once Phase 1 is complete.

### Phase 1 – Core runtime modules (strict typing required)
Focus on modules that influence request handling and domain serialization.
- `theo/services/api/app/core`
- `theo/services/api/app/models`
- `theo/services/api/app/routes`
- `theo/services/api/app/telemetry`
- `theo/services/api/app/db`

Deliverables:
- Remove or replace blanket ignores with targeted error-code suppressions.
- Bring each module to `strict = True` (or an equivalent `pyproject.toml` override) and
  eliminate remaining `Any`-typed inheritance chains.
- Introduce regression tests or sample typings that keep plugin integrations (e.g.,
  Pydantic `BaseSettings`) typed.
- Reduce unused ignores in these modules to zero so that `warn-unused-ignores` can pass.

### Phase 2 – Ingest, export, and AI coordination modules
Once the runtime core is stable, expand to the heavier business logic packages.
- `theo/services/api/app/ingest`
- `theo/services/api/app/export`
- `theo/services/api/app/ai`
- `theo/services/api/app/analytics`
- `theo/services/api/app/retriever`
- `theo/services/api/app/case_builder`
- `theo/services/api/app/workers`

Deliverables:
- Apply the same strictness criteria as Phase 1.
- Replace broad container-typed signatures (`dict`, `list`, `OrderedDict`) with concrete
  generics to eliminate `Any` propagation.
- Ensure long-running background tasks and ingest pipelines have typed boundaries so that
  downstream teams can build on reliable contracts.
- Track any remaining ignores that cannot be removed (e.g., third-party library gaps) in a
  shared issue list, tagged by module owners.

### Phase 3 – Remaining services and regression guardrails
Complete coverage by addressing lower-risk modules and reinforcing automation.
- Extend strictness to the remaining packages under `theo/services/api/app` (e.g.,
  `intent`, `debug`, `mcp`, `ranking`, `research`, `transcripts`, `notebooks`, and
  `services`).
- Bring `tests/export` and other test suites under the same strictness rules when they
  import typed helpers.
- Turn on `warn-unused-ignores` as a required CI check by flipping the workflow toggle
  introduced in Phase 0.
- Add documentation to contributor guides that codifies the expectation for new `# type:
  ignore` comments (must include error codes and follow-up issues when necessary).

### Treatment of remaining ignores
- Each phase includes an ignore review: comments must either be deleted, replaced with a
  specific error-code suppression, or explicitly linked to a tracking ticket.
- Any ignore kept past Phase 2 must be justified in the module’s README or docstring with a
  pointer to the blocking issue (e.g., missing upstream types).
- Once `warn-unused-ignores` is enforced in CI, new ignores without an error code or
  tracking note will fail the build.

## Consequences
- The team has a concrete sequence of modules to prioritize, making it easier to parallelize
  work and understand when the CI toggle can be flipped on.
- Documentation and workflow updates ensure that new code converges toward strict typing
  instead of reintroducing broad ignores.
- The roadmap creates checkpoints for measuring progress (e.g., number of ignores remaining
  per module) and provides clarity on when `warn-unused-ignores` becomes mandatory.
