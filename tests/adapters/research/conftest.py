import importlib
import sys
import types

if "theo.infrastructure.api.app.workers.tasks" not in sys.modules:
    try:
        importlib.import_module("theo.infrastructure.api.app.workers.tasks")
    except Exception:
        workers_pkg = importlib.import_module("theo.infrastructure.api.app.workers")
        celery_stub = types.SimpleNamespace(
            conf=types.SimpleNamespace(
                task_always_eager=False,
                task_ignore_result=False,
                task_store_eager_result=False,
            )
        )
        stub_module = types.ModuleType("theo.infrastructure.api.app.workers.tasks")
        stub_module.celery = celery_stub
        sys.modules[stub_module.__name__] = stub_module
        setattr(workers_pkg, "tasks", stub_module)
