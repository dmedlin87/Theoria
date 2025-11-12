# Worker Test Harness

The worker test suites rely on `tests/workers/conftest.py` to isolate Celery tasks
from heavyweight integrations. The `worker_stubs` fixture configures the
`WorkerStubContext`, which injects deterministic stand-ins for dependencies such as
pipeline orchestrators, hybrid search, topic digests, and HTTP clients.

To keep the stubs effective:

* Always import task callables via `theo.infrastructure.api.app.workers.tasks`
  after calling `configure_worker_dependencies` in the tests. This ensures tasks
  use the fake clients instead of real services.
* Prefer serializable structures (plain dicts or dataclasses with `model_dump`)
  when constructing chat memories or citations. The helper `_json_default`
  normalises deliverable manifests and cached citations for snapshot-style
  assertions.
* Add new optional dependencies to `WorkerStubContext.dependencies` so that
  future worker behaviours remain deterministic during testing.

Run the worker suites with:

```bash
pytest tests/workers/test_tasks.py \
       tests/workers/test_tasks_optimized.py \
       tests/workers/test_tasks_perf_patch.py
```

The tests execute quickly (under a second) when the stubs are active, and they do
not require optional modules like `pythonbible`, `rag`, or HTTP transport packages.
