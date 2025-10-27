# Pytest performance monitoring

This document captures the workflow for profiling the expensive opt-in pytest
suites that are gated behind the `schema`, `pgvector`, and `contract` markers.
It covers local profiling, CI integration, and how the resulting metrics are
tracked over time.

## Marker profiling script

Run the helper script to execute each opt-in suite with `--durations` enabled
and persist JSON output under `perf_metrics/`:

```bash
python scripts/perf/profile_marker_suites.py
```

The script can target a subset of markers if you only want to profile a single
suite:

```bash
python scripts/perf/profile_marker_suites.py contract
```

Profiles are stored in `perf_metrics/pytest_marker_baselines.json`. Commit the
updated file whenever a notable change lands (new fixtures, migrations, or
schema-heavy refactors) so we can compare historical execution times.

## Transactional isolation for schema tests

`@pytest.mark.schema` tests now automatically opt into the `schema_isolation`
fixture. The fixture wraps each test function in a database transaction that is
rolled back at teardown, while the companion `integration_session` fixture
provides a SQLAlchemy `Session` pre-bound to that transaction. This keeps the
integration database clean between tests and avoids the previous need to
recreate schemas from scratch.

## CI monitoring

The `heavy-tests` matrix job in `.github/workflows/ci.yml` calls the profiling
script for each marker suite. The job enables `pytest-xdist` with
`--dist=loadscope` so tests that do not share state can run in parallel. Each
run uploads a `pytest-<marker>-profile` artifact containing the JSON timings,
which makes it easy to spot regressions straight from the Actions UI.

## Baselines

The repository tracks the latest baseline timings in
`perf_metrics/pytest_marker_baselines.json`. Treat these values as guidance when
reviewing PRs: a significant increase in any suite should either be justified in
the change description or followed by optimisation work. When the JSON contains
`0.0` timings it simply indicates that the profiling script has not been run in
a fully provisioned environment yet; regenerate the file locally before relying
on those figures.
