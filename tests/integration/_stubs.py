from __future__ import annotations

import sys
import types


def install_sklearn_stub() -> None:
    """Install lightweight sklearn replacements used in integration tests."""

    if "sklearn" in sys.modules:
        return

    sklearn_module = types.ModuleType("sklearn")
    ensemble_module = types.ModuleType("sklearn.ensemble")
    cluster_module = types.ModuleType("sklearn.cluster")

    class _StubIsolationForest:
        def __init__(self, *_, **__) -> None:
            return None

        def fit(self, *_args, **_kwargs):
            return self

        def decision_function(self, embeddings):
            return [0.0 for _ in range(len(embeddings) or 0)]

        def predict(self, embeddings):
            return [1 for _ in range(len(embeddings) or 0)]

    ensemble_module.IsolationForest = _StubIsolationForest  # type: ignore[attr-defined]
    sklearn_module.ensemble = ensemble_module  # type: ignore[attr-defined]

    class _StubDBSCAN:
        def __init__(self, *_, **__) -> None:
            return None

        def fit_predict(self, embeddings):
            return [0 for _ in range(len(embeddings) or 0)]

    cluster_module.DBSCAN = _StubDBSCAN  # type: ignore[attr-defined]
    sklearn_module.cluster = cluster_module  # type: ignore[attr-defined]

    sys.modules["sklearn"] = sklearn_module
    sys.modules["sklearn.ensemble"] = ensemble_module
    sys.modules["sklearn.cluster"] = cluster_module


def install_celery_stub() -> None:
    """Install a pared-down Celery facade for environments without the dependency."""

    if "celery" in sys.modules:
        return

    celery_module = types.ModuleType("celery")

    class _StubCelery:
        def __init__(self, *_, **__) -> None:
            self.conf = types.SimpleNamespace(
                task_always_eager=True,
                task_ignore_result=True,
                task_store_eager_result=False,
            )

        def task(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    celery_module.Celery = _StubCelery  # type: ignore[attr-defined]

    celery_app_module = types.ModuleType("celery.app")
    celery_task_module = types.ModuleType("celery.app.task")

    class _StubTask:
        abstract = False

    celery_task_module.Task = _StubTask  # type: ignore[attr-defined]
    celery_app_module.task = celery_task_module  # type: ignore[attr-defined]

    celery_exceptions_module = types.ModuleType("celery.exceptions")

    class _StubRetry(Exception):
        pass

    celery_exceptions_module.Retry = _StubRetry  # type: ignore[attr-defined]

    celery_schedules_module = types.ModuleType("celery.schedules")

    def _crontab(*_args, **_kwargs):
        return {"type": "crontab"}

    celery_schedules_module.crontab = _crontab  # type: ignore[attr-defined]

    celery_utils_module = types.ModuleType("celery.utils")
    celery_utils_log_module = types.ModuleType("celery.utils.log")

    def _get_task_logger(name: str):
        class _StubLogger:
            def info(self, *_args, **_kwargs):
                return None

            def error(self, *_args, **_kwargs):
                return None

        return _StubLogger()

    celery_utils_log_module.get_task_logger = _get_task_logger  # type: ignore[attr-defined]
    celery_utils_module.log = celery_utils_log_module  # type: ignore[attr-defined]

    sys.modules["celery"] = celery_module
    sys.modules["celery.app"] = celery_app_module
    sys.modules["celery.app.task"] = celery_task_module
    sys.modules["celery.exceptions"] = celery_exceptions_module
    sys.modules["celery.schedules"] = celery_schedules_module
    sys.modules["celery.utils"] = celery_utils_module
    sys.modules["celery.utils.log"] = celery_utils_log_module

    celery_result_module = types.ModuleType("celery.result")

    class _StubAsyncResult:
        def __init__(self, task_id: str, *_, **__) -> None:
            self.id = task_id
            self.state = "SUCCESS"

        def ready(self) -> bool:
            return True

        def get(self, *_, **__):
            return None

    celery_result_module.AsyncResult = _StubAsyncResult  # type: ignore[attr-defined]
    sys.modules["celery.result"] = celery_result_module


__all__ = ["install_celery_stub", "install_sklearn_stub"]
