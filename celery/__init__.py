"""Lightweight Celery stubs used in optional test environments.

This module provides a minimal subset of the public Celery API sufficient for
unit tests that exercise Theoria's worker task wiring.  The real Celery
dependency is quite heavy and not required for these isolated suites, so the
project ships a tiny shim that mimics the handful of behaviours relied upon by
the tests (task registration, eager execution helpers, and logging).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Iterable

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

    def send_task(self, name: str, args: Iterable[Any] | None = None, kwargs: dict[str, Any] | None = None) -> Any:
        """Execute a registered task synchronously.

        The stub mimics Celery's eager execution semantics by delegating to the
        task's ``run`` method if it has been registered.  It is intentionally
        small and only implements the behaviour needed in the worker tests.
        """

        task = self.tasks.get(name)
        if task is None:
            raise KeyError(f"Task {name!r} is not registered with this Celery app")
        return task.run(*(args or ()), **(kwargs or {}))
