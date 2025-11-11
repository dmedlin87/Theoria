"""Site customization for Theoria to handle conditional imports gracefully.

This module stubs heavy dependencies like Celery and workers when they're
optionally not installed, preventing ImportError in lighter test environments.
"""

from __future__ import annotations

import builtins
import importlib
import importlib.util
import os
import sys
import types
from typing import Any
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent

_existing_celery = sys.modules.get("celery")
if _existing_celery is not None and not hasattr(_existing_celery, "__path__"):
    try:
        _existing_celery.__path__ = [  # type: ignore[attr-defined]
            str(_REPO_ROOT / "celery")
        ]
    except Exception:
        pass

_WORKERS_TASKS_MODULE = "theo.infrastructure.api.app.workers.tasks"
_FASTAPI_MODULE = "fastapi"
_FASTAPI_STATUS_MODULE = "fastapi.status"
_CELERY_PLUGIN_MODULE = "celery.contrib.pytest"


def _install_fastapi_stub() -> None:
    """Install a minimal FastAPI status stub when the dependency is missing."""

    if _FASTAPI_STATUS_MODULE in sys.modules:
        return

    fastapi_module = types.ModuleType(_FASTAPI_MODULE)
    status_module = types.ModuleType(_FASTAPI_STATUS_MODULE)
    setattr(status_module, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
    sys.modules[_FASTAPI_STATUS_MODULE] = status_module
    fastapi_module.status = status_module  # type: ignore[attr-defined]
    sys.modules[_FASTAPI_MODULE] = fastapi_module


def _ensure_fastapi_modules_loaded() -> None:
    """Guarantee FastAPI status shim is available before project imports."""

    try:
        importlib.import_module(_FASTAPI_MODULE)
        importlib.import_module(_FASTAPI_STATUS_MODULE)
    except (ModuleNotFoundError, ImportError):
        _install_fastapi_stub()


_ensure_fastapi_modules_loaded()


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
        try:
            return original_import(name, globals, locals, fromlist, level)
        except ImportError as exc:
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

            if _CELERY_PLUGIN_MODULE in requested:
                repo_root = _REPO_ROOT
                if str(repo_root) not in sys.path:
                    sys.path.insert(0, str(repo_root))
                mod = sys.modules.get("celery")
                if mod is not None and not hasattr(mod, "__path__"):
                    del sys.modules["celery"]
                try:
                    return original_import(name, globals, locals, fromlist, level)
                except ImportError:
                    try:
                        plugin_path = (repo_root / "celery" / "contrib" / "pytest.py").resolve()
                        if plugin_path.exists():
                            # Ensure parent package objects exist
                            celery_pkg = sys.modules.get("celery")
                            if celery_pkg is None:
                                try:
                                    celery_pkg = importlib.import_module("celery")
                                except Exception:
                                    celery_pkg = types.ModuleType("celery")
                                    # Ensure the stub behaves like a package so submodules
                                    # such as ``celery.contrib`` import without raising the
                                    # ``'celery' is not a package`` error observed on Windows
                                    # test environments.
                                    celery_pkg.__path__ = [  # type: ignore[attr-defined]
                                        str(repo_root / "celery")
                                    ]
                                    sys.modules["celery"] = celery_pkg
                            elif not hasattr(celery_pkg, "__path__"):
                                celery_pkg.__path__ = [  # type: ignore[attr-defined]
                                    str(repo_root / "celery")
                                ]
                            contrib_name = "celery.contrib"
                            contrib_mod = sys.modules.get(contrib_name)
                            if contrib_mod is None:
                                contrib_mod = types.ModuleType(contrib_name)
                                setattr(celery_pkg, "contrib", contrib_mod)  # type: ignore[attr-defined]
                                sys.modules[contrib_name] = contrib_mod
                            spec = importlib.util.spec_from_file_location(
                                "celery.contrib.pytest", str(plugin_path)
                            )
                            if spec and spec.loader:
                                plugin_mod = importlib.util.module_from_spec(spec)
                                sys.modules["celery.contrib.pytest"] = plugin_mod
                                setattr(contrib_mod, "pytest", plugin_mod)  # type: ignore[attr-defined]
                                spec.loader.exec_module(plugin_mod)
                                return plugin_mod
                    except Exception:
                        pass

            if (
                _WORKERS_TASKS_MODULE not in requested
                or _WORKERS_TASKS_MODULE in sys.modules
            ):
                raise exc

            _install_workers_stub()

            return original_import(name, globals, locals, fromlist, level)

    builtins.__import__ = guarded_import  # type: ignore[assignment]
    _register_workers_import_fallback._installed = True  # type: ignore[attr-defined]


_register_workers_import_fallback()

if _WORKERS_TASKS_MODULE not in sys.modules:  # pragma: no cover - import-time wiring only
    if _should_install_workers_stub():
        _install_workers_stub()
try:
    importlib.import_module("theo.infrastructure.api.app.workers.tasks")
except Exception:  # pragma: no cover - executed only when optional deps missing
    _install_workers_stub()
