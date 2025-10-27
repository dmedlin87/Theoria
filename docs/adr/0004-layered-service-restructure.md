# ADR 0004: Establish Domain/Application/Infrastructure Service Boundaries

- Status: Accepted
- Date: 2025-10-27

## Context

Service modules previously lived under the flat ``theo.services`` namespace.
The directory mixed HTTP adapters, CLI entry points, and domain orchestration
utilities, which made it difficult to reason about layering rules. Existing
contracts relied on negative checks ("domain cannot import services") instead
of expressing the intended domain → application → delivery flow directly.

## Decision

- Introduce dedicated packages for each layer:
  - ``theo/domain/services/`` for domain-centric orchestration helpers (e.g.,
    embedding rebuild instrumentation).
  - ``theo/application/services/`` for application services and CLI commands
    that coordinate infrastructure adapters.
  - ``theo/infrastructure/api/`` (and related namespaces such as
    ``theo/infrastructure/web/``) for delivery mechanisms and framework
    integrations.
- Move the embedding and geospatial loaders, CLI tools, and bootstrap helpers
  into the appropriate domain or application packages.
- Relocate HTTP adapters and API runtime under ``theo.infrastructure``.
- Update imports, tests, and import-linter contracts so the layering contract is
  enforced as ``theo.domain → theo.application → theo.infrastructure``.

## Consequences

- The layering intent is now encoded directly in the package structure, making
  dependency violations easier to detect in code reviews.
- Tooling (architecture tests, Import Linter) can assert that application code
  never reaches into infrastructure packages and that domain code remains
  infrastructure-agnostic.
- Contributors migrating legacy modules should move them into the relevant
  package before exposing new imports. When porting code, follow these
  guidelines:
  - Domain logic (schema transforms, scoring algorithms) belongs in
    ``theo.domain`` or ``theo.domain.services``.
  - Application coordination (facades, CLI entry points, background workflows)
    belongs in ``theo.application``.
  - Framework-specific delivery (FastAPI routes, Celery workers, web UI) belongs
    in ``theo.infrastructure``.
- Historical references to ``theo.services`` should be updated incrementally;
  compatibility shims should not be reintroduced under the old namespace.
