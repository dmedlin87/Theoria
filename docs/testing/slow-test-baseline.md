# Slow Test Baseline

The slow test baseline helps identify the flakiest tests by repeatedly running
pytest's slowest test cases and saving their results for review.

## Running the baseline

```bash
# Execute the task from the project root
poetry install  # only needed once to ensure dependencies are present
task test:slow-baseline
```

The task runs `pytest --durations=50 --durations-min=0.05` to capture the 50
slowest tests that take at least 50ms. Each test is then re-executed 20 times.

You can pass additional pytest flags or change the repeat count directly via the
underlying script:

```bash
poetry run python scripts/perf/slow_test_baseline.py --repeat 5 --pytest-args "-m slow"
```

## Reviewing artifacts

Each invocation creates a timestamped folder under `logs/test-baseline/` with
these files:

- `durations.log` – full output from the initial discovery run.
- `summary.json` – machine-readable record of every rerun and result code.
- One subdirectory per test (sanitized nodeid) containing paired
  `run_<NN>.xml` and `run_<NN>.json` reports for each rerun.

Failures are surfaced by a non-zero exit code so the task can fail CI when a
rerun fails. Review `summary.json` or the per-test JSON files to spot flaky
cases and determine if quarantine or fixes are required. For historical tracking
commit the artifact directory to long-term storage or ingest the JSON payloads
into your preferred observability tool.
