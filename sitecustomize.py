"""Site customization for Theoria to handle conditional imports gracefully.

This module stubs heavy dependencies like Celery and workers when they're
optionally not installed, preventing ImportError in lighter test environments.
"""

from __future__ import annotations

import builtins
import importlib
import os
import sys
import types
from typing import Any

_WORKERS_TASKS_MODULE = "theo.services.api.app.workers.tasks"


def _should_install_workers_stub() -> bool:
    """Check if workers stub should be installed."""
    return (
        os.environ.get("THEORIA_SKIP_HEAVY_FIXTURES", "0") in {"1", "true", "TRUE"}
        or "pytest" in sys.modules
    )


def _install_workers_stub() -> None:
    """Install a minimal workers stub to prevent ImportError."""
    if _WORKERS_TASKS_MODULE in sys.modules:
        return

    workers_pkg = importlib.import_module("theo.services.api.app.workers")
    celery_stub = types.SimpleNamespace(
        conf=types.SimpleNamespace(
            task_always_eager=False,
            task_ignore_result=False,
            task_store_eager_result=False,
        )
    )
    stub_module = types.ModuleType(_WORKERS_TASKS_MODULE)
    stub_module.celery = celery_stub
    sys.modules[stub_module.__name__] = stub_module
    setattr(workers_pkg, "tasks", stub_module)


def _register_workers_import_fallback() -> None:
    """Register import hook that stubs workers on ImportError."""
    if getattr(_register_workers_import_fallback, "_installed", False):  # pragma: no cover
        return

    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        """Wrap __import__ to stub workers.tasks on ImportError."""
        try:
            return original_import(name, globals, locals, fromlist, level)
        except ImportError as exc:
            # Only intercept workers.tasks imports specifically
            if name != _WORKERS_TASKS_MODULE:
                raise exc

            # Build the set of all requested modules
            absolute = name
            if level > 0 and globals is not None:
                package = globals.get("__package__")
                if package:
                    if level == 1:
                        absolute = f"{package}.{name}" if name else package
                    else:
                        parts = package.split(".")
                        if len(parts) >= level - 1:
                            base = ".".join(parts[: -(level - 1)])
                            absolute = f"{base}.{name}" if name else base

            requested = {absolute}

            if fromlist:
                for entry in fromlist:
                    if entry in {"", "*"}:
                        continue
                    requested.add(f"{absolute}.{entry}")

            if (
                _WORKERS_TASKS_MODULE not in requested
                or _WORKERS_TASKS_MODULE in sys.modules
            ):
                raise exc

            _install_workers_stub()

            return original_import(name, globals, locals, fromlist, level)

    builtins.__import__ = guarded_import  # type: ignore[assignment]
    _register_workers_import_fallback._installed = True  # type: ignore[attr-defined]


if _WORKERS_TASKS_MODULE not in sys.modules:  # pragma: no cover - import-time wiring only
    if _should_install_workers_stub():
        _install_workers_stub()
    else:
        _register_workers_import_fallback()
try:
    importlib.import_module("theo.services.api.app.workers.tasks")
except Exception:  # pragma: no cover - executed only when optional deps missing
    workers_pkg = importlib.import_module("theo.services.api.app.workers")
    celery_stub = types.SimpleNamespace(
        conf=types.SimpleNamespace(
            task_always_eager=False,
            task_ignore_result=False,
            task_store_eager_result=False,
        )
    )
    stub_module = types.ModuleType("theo.services.api.app.workers.tasks")
    stub_module.celery = celery_stub
    sys.modules[stub_module.__name__] = stub_module
    setattr(workers_pkg, "tasks", stub_module)
