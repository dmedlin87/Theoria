# ADR 0001: Adopt Hexagonal Architecture with Domain-Centric Modules

- Status: Accepted
- Date: 2024-05-01

## Context

The existing codebase couples FastAPI controllers, Celery workers, and persistence layers directly, making it difficult to add new adapters or reason about business rules. We need strict boundaries so the domain can evolve independently of framework choices.

## Decision

- Introduce new packages: `theo.domain`, `theo.application`, `theo.adapters` (legacy `theo.platform` responsibilities now live within `theo.application.services`).
- Define ports and facades in the application layer; domain exports value objects only.
- Framework-specific code lives in adapters that depend on ports, never on the reverse.
- Enforce layering via automated architecture tests.

## Consequences

- Short-term increase in indirection while compatibility facades coexist with legacy modules.
- Enables testing domain logic without FastAPI or database dependencies.
- Simplifies addition of new delivery mechanisms (e.g., GraphQL, MCP) without touching core logic.
