# Architecture Dependency Boundaries

The Theo codebase follows a layered architecture that keeps the domain model
isolated from infrastructure concerns. The enforced dependency direction is:

```
theo.domain  →  theo.application  →  theo.infrastructure
```

* **Domain (`theo.domain`)** contains core business concepts. It must not depend
  on the application or infrastructure layers.
* **Application (`theo.application`)** coordinates domain workflows and exposes
  facades for downstream adapters. It may import the domain layer (and vetted
  adapter abstractions), but it must not reach into infrastructure runtimes or
  framework code such as FastAPI.
* **Infrastructure (`theo.infrastructure`)** provides delivery mechanisms (API,
  CLI orchestration, web UI) and may depend on both the application and domain
  layers.

## Enforced rules

The dependency graph is verified in two complementary ways:

1. **Architecture tests** (`tests/architecture/test_module_boundaries.py`)
   assert that application modules never import
   `theo.infrastructure.api.app.*`, the telemetry/resilience/security adapters, or
   `fastapi`. Existing tests also prevent domain modules from depending on
   services and ensure other adapter constraints.
2. **Import Linter** (`importlinter.ini`) encodes the layered contract so that
   no package can import “up” the stack. Any attempt to import from services to
   application (or from application to domain) will fail the lint step.

## Running the checks locally

Use the Taskfile helpers to execute the architecture guardrails:

```sh
# run only the architecture-focused pytest suite
task architecture:test

# run the import-linter contracts
task architecture:imports

# run both together
task architecture:check
```

These commands run automatically in CI to block merges that break the enforced
module boundaries.

## Visualising the dependency graph

Generate snapshot artefacts with the Taskfile helper:

```sh
task architecture:graph
```

The command writes `dependency-graph.json` and `dependency-graph.svg` into
`dashboard/dependency-graph/`. Commit these files whenever the architecture
changes so reviewers can inspect the rendered diagram. To check for drift
between branches, compare the JSON metadata (`git diff -- dashboard/dependency-graph/dependency-graph.json`)
or open the SVGs in a viewer and toggle between versions.
