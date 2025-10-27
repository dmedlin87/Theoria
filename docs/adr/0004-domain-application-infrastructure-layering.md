# ADR 0004: Consolidate Services into Domain/Application/Infrastructure Layers

- Status: Accepted
- Date: 2025-10-27

## Context

The legacy `theo.services` namespace mixed domain orchestration, CLI tooling,
background workers, and HTTP adapters. This blurred boundaries originally
established by ADR 0001 (Hexagonal Architecture) and made it difficult to
reason about which modules could reference external frameworks. We needed a
clear migration path that aligned implementation with the conceptual
Domain→Application→Infrastructure layering enforced elsewhere in the codebase.

## Decision

- Introduce dedicated packages for the service split:
  - `theo/domain/services/` for domain-centric helpers such as embedding
    rebuild configuration.
  - `theo/application/services/` for orchestration utilities, CLI entry
    points, and data seeding workflows.
  - `theo/infrastructure/api/` for FastAPI adapters, background workers, and
    other HTTP-facing concerns.
- Move embedding and geospatial helpers out of `theo.services` into the new
  domain/application packages and adjust imports across the repository.
- Update import-linter contracts so the layering contract explicitly orders
  `theo.infrastructure` → `theo.application` → `theo.domain`.
- Refresh architecture tests and developer tooling to reference the new
  namespaces.

## Consequences

- The `theo.services` package now exists only as a compatibility shim; new
  code should import directly from `theo.domain.services`,
  `theo.application.services`, or `theo.infrastructure`.
- Automation, documentation, and linting configuration required updates to
  point at the new paths.
- Layering rules are stricter: application modules cannot import
  infrastructure adapters, and domain modules remain isolated from both.

## Migration Guidelines

- Update imports by replacing `theo.services.api` with
  `theo.infrastructure.api`, `theo.services.cli` with
  `theo.application.services.cli`, and `theo.services.embeddings` with
  `theo.domain.services.embeddings`.
- CLI entry points should resolve application state via
  `theo.application.services.bootstrap.resolve_application`.
- Infrastructure adapters that need domain logic should depend on
  application facades (`theo.application.facades.*`) instead of reaching back
  into infrastructure modules.
- When adding new service code, choose the package based on responsibility:
  domain logic lives under `theo/domain/services/`, orchestration and data
  ingestion under `theo/application/services/`, and HTTP or worker adapters
  under `theo/infrastructure/`.
