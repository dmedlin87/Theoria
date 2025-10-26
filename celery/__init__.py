"""Expose the real :mod:`celery` package when available.

The repository ships a small Celery shim so worker-related tests can execute in
lightweight environments.  Whenever the genuine dependency is present we defer
to it to match production behaviour.  Only when the package is missing do we
provide the stub below, which implements the narrow surface area exercised by
the test suite.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Callable, Iterable


def _import_real_module(name: str) -> ModuleType | None:
    """Attempt to load *name* from site-packages instead of the repo stub."""

    repo_root = Path(__file__).resolve().parents[1]
    original_sys_path = list(sys.path)
    filtered_sys_path: list[str] = []
    removed_repo_root = False
    for entry in original_sys_path:
        to_resolve = entry or "."
        try:
            resolved = Path(to_resolve).resolve()
        except Exception:  # pragma: no cover - extremely defensive
            filtered_sys_path.append(entry)
            continue
        if resolved == repo_root:
            removed_repo_root = True
            continue
        filtered_sys_path.append(entry)

    if not removed_repo_root:
        return None

    existing_module = sys.modules.get(name)
    module: ModuleType | None = None
    try:
        if name in sys.modules:
            del sys.modules[name]
        sys.path = filtered_sys_path
        module = importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if getattr(exc, "name", name) != name:
            raise
        module = None
    finally:
        sys.path = original_sys_path
        if module is None and existing_module is not None:
            sys.modules[name] = existing_module

    return module


_real_celery = _import_real_module("celery")
if _real_celery is not None:
    sys.modules[__name__] = _real_celery
    globals().update({key: getattr(_real_celery, key) for key in dir(_real_celery)})
    __all__ = getattr(_real_celery, "__all__", [key for key in dir(_real_celery) if not key.startswith("_")])
else:
    from .app.task import Task
    from .exceptions import Retry

    __all__ = ["Celery", "Retry"]

    class Celery:
        """A drastically simplified stand-in for :class:`celery.Celery`."""

        def __init__(self, main: str, *, broker: str | None = None, backend: str | None = None) -> None:
            self.main = main
            self.broker = broker
            self.backend = backend
            self.conf = SimpleNamespace(
                task_always_eager=False,
                task_eager_propagates=False,
                task_ignore_result=False,
                task_store_eager_result=False,
                beat_schedule={},
            )
            self.tasks: dict[str, Task] = {}

        def task(
            self,
            name: str | None = None,
            *,
            bind: bool = False,
            max_retries: int | None = None,
            **_opts: Any,
        ) -> Callable[[Callable[..., Any]], Task]:
            """Register a callable as a task and return a :class:`Task` wrapper."""

            def decorator(func: Callable[..., Any]) -> Task:
                task_name = name or func.__name__
                task = Task(
                    func=func,
                    app=self,
                    name=task_name,
                    bind=bind,
                    max_retries=max_retries if max_retries is not None else 3,
                )
                self.tasks[task_name] = task
                return task

            return decorator

        def send_task(
            self,
            name: str,
            args: Iterable[Any] | None = None,
            kwargs: dict[str, Any] | None = None,
        ) -> Any:
            """Execute a registered task synchronously.

            The stub mimics Celery's eager execution semantics by delegating to the
            task's ``run`` method if it has been registered.  It is intentionally
            small and only implements the behaviour needed in the worker tests.
            """

            task = self.tasks.get(name)
            if task is None:
                raise KeyError(f"Task {name!r} is not registered with this Celery app")
            return task.run(*(args or ()), **(kwargs or {}))
