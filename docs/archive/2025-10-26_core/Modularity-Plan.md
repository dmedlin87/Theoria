> **Archived on 2025-10-26**

# Modularity Refactor Plan (Hexagonal Architecture)

## Target Architecture Overview

```
┌───────────────────┐      Inbound Ports      ┌────────────────────────┐
│   Interface Ring   │ ─────────────────────▶ │   Application Services  │
│ (API / CLI / Web)  │ ◀───────────────────── │ (Command + Query use    │
└───────────────────┘      Outbound Ports      │  cases, Orchestrators) │
          ▲                                    └──────────┬────────────┘
          │                                               │
          │                                      Domain Ports (events,
          │                                         repositories)
          │                                               │
┌─────────┴────────┐                              ┌───────▼────────────┐
│ Infrastructure / │ ◀──────────────────────────▶ │   Domain Core      │
│    Adapters      │      Driven Ports            │ (Entities, Value   │
│ (DB, Vector, LLM │                              │  Objects, Policies)│
│   clients, etc.) │                              └────────────────────┘
└──────────────────┘
```

## Module Boundaries

| Module | Responsibility | Inbound Ports | Outbound Ports | Notes |
| --- | --- | --- | --- | --- |
| `theo.domain` | Pure business concepts (documents, scripture refs, research tasks) | Event handlers (domain events), repositories as interfaces | Domain events, repository contracts | No framework imports; only stdlib/pydantic.
| `theo.application` | Use-cases orchestrating domain logic | API commands, CLI commands, scheduled jobs | Repository interfaces, notification gateways, search/vector clients | Depends on domain contracts only.
| `theo.adapters.persistence` | Postgres/SQLite ORM models, Redis caches | Repository interfaces from application/domain | SQLAlchemy sessions, migration tooling | Implements `theo.domain.repositories` protocols.
| `theo.adapters.search` | Vector + lexical search connectors | Query ports from application | HTTP clients, embeddings | Wraps providers behind typed ports.
| `theo.adapters.ai` | LLM provider implementations | Workflow service ports | Calls out to OpenAI/Anthropic/local engines.
| `theo.adapters.interfaces.api` | FastAPI routes/controllers | HTTP requests | Calls application services | Sole entry for REST.
| `theo.adapters.interfaces.cli` | CLI commands / scripts | CLI invocations | Application service interfaces | No direct DB access.
| `theo.adapters.interfaces.web` | Next.js proxy + UI integration | HTTP/GraphQL boundary | REST/WS API only | Lives in separate package; interacts via HTTP clients.
| `theo.platform` | Cross-cutting infrastructure (telemetry, security policies, settings) | Application bootstrap | Logging, tracing sinks | Provides adapters with shared utilities.

## Ports & Contracts

### Inbound (Driving) Ports
- `theo.application.ports.commands` – CRUD & ingestion commands invoked by API/CLI.
- `theo.application.ports.queries` – Search, ranking, research queries triggered by API/Web.
- `theo.application.ports.schedules` – Background tasks & Celery worker triggers.

### Outbound (Driven) Ports
- `theo.domain.repositories` – Persistence contracts (documents, verses, jobs, providers).
- `theo.application.ports.notifications` – Webhooks, email, Slack connectors.
- `theo.application.ports.search` – Embeddings + lexical search integration.
- `theo.application.ports.ai` – LLM completion/streaming interfaces.
- `theo.platform.telemetry` – Metrics/tracing collectors.

## Public APIs Per Module

- `theo.domain` exports immutable data classes, aggregates, and domain services through `__all__` definitions. No module may import from `theo.adapters.*`.
- `theo.application` exposes orchestrator classes (`IngestDocumentService`, `ResearchWorkflowService`) via dedicated `facade` modules that depend solely on ports.
- `theo.adapters.*` modules implement the respective port interfaces and are registered via dependency injection container (`theo.platform.bootstrap`).
- `theo.adapters.interfaces.*` provide boundary controllers; they **MUST** invoke application facades only.

### Forbidden Couplings

- Cross-adapter imports (e.g., `adapters.persistence` importing `adapters.ai`).
- Interface layers bypassing application services.
- Domain layer referencing FastAPI, SQLAlchemy, or Celery types.
- Application layer instantiating infrastructure classes directly (use factory functions defined in bootstrap).

## Enforcement Strategy

1. **Architecture Tests:** `tests/architecture/test_module_boundaries.py` parses AST imports to fail on forbidden edges.
2. **Code Owners:** Assign CODEOWNERS per module (future work) to enforce review expertise.
3. **Lint Gates:** Extend Ruff custom ruleset to forbid banned import patterns once module move completes.
4. **CI Validation:** Architecture tests + mypy strict mode guard adapters from leaking framework-only symbols into domain/application layers.

## Migration Plan

### Phase 1 – Foundations (Current)
- Introduce module scaffolding (`theo/domain`, `theo/application`, `theo/adapters`, `theo/platform`).
- Provide compatibility facades that wrap existing services and expose planned interfaces.
- Add architecture tests & CI guardrails.

### Phase 2 – Extract Domain & Application
- Move pure business logic from `theo/services/api/app/core/*` and `.../research/*` into `theo.domain`.
- Replace direct SQLAlchemy imports with repository protocols implemented in `theo.adapters.persistence`.
- Introduce DTO mappers between FastAPI schemas and domain aggregates.

### Phase 3 – Adapter Isolation
- Relocate HTTP clients (OpenAI, Anthropic, etc.) under `theo.adapters.ai` with configuration objects.
- Wrap Celery tasks and background workers via application schedules ports.
- Ensure CLI uses application services via dependency-injected container (no direct DB usage).

### Phase 4 – Eventing & Extensibility
- Publish domain events through `theo.platform.events` to allow new adapters (e.g., auditing, analytics) without touching core.
- Document extension points and register entrypoints for plugin discovery.

## Diagram Legend

- **Inbound Ports:** Interfaces consumed by driving adapters (API/CLI/Web).
- **Outbound Ports:** Interfaces implemented by driven adapters (DB, LLM, notifications).
- **Facades:** `theo.application.facades` unify domain operations for adapters.
- **Events:** Domain events emitted via `theo.platform.events` for asynchronous reactions.

## Next Steps Checklist

- [ ] Create compatibility layers mapping old module paths to new facades (deprecate direct imports).
- [ ] Update FastAPI routes to depend on `theo.application` services only.
- [ ] Add adapter registration to worker entry points and CLI scripts.
- [ ] Expand architecture tests to cover async task graph once Celery refactor completes.
