# Test Runbook

The pytest configuration in `pyproject.toml` enforces strict marker usage, a 60
second timeout per test via `pytest-timeout`, and deterministic ordering via
`pytest-randomly` (seeded to `1337`). Coverage is disabled by default for faster
feedback; run `pytest --cov=theo --cov-report=term-missing --cov-report=xml --cov-fail-under=80`
when coverage is required.

## Local fast loop

```bash
pytest -q -k "not slow and not e2e" --ff --maxfail=1
```

### Lightweight dependency mode

Set `THEORIA_SKIP_HEAVY_FIXTURES=1` when iterating on the ingest and worker
pipelines to skip optional third-party fixtures (FastAPI, Opentelemetry, etc.)
that are not required for those suites. This trims import time and avoids
installing large stacks while preserving default behaviour for the broader
test harness.

## Profiling mode

```bash
pytest --durations=25 --durations-min=0.05 -q
```

## Parallel smoke

```bash
pytest -n auto -m "not slow and not e2e" -q
```

## Full CI (pull requests)

```bash
pytest -n auto -m "not slow and not e2e" --strict-markers --durations=25
```

Use `pytest-split` with historical durations when distributing tests across
multiple runners, for example:

```bash
pytest -n auto --splits <total-splits> --group <group-index>
```

## Nightly / comprehensive suite

```bash
pytest -n auto -m "slow or e2e" --benchmark-only
```

The nightly job is the place to combine coverage, slow/e2e selections, and
long-running benchmarks.
