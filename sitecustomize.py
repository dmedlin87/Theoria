from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import types
import warnings

# Suppress noisy deprecation warnings emitted by schemathesis' dependency on
# jsonschema internals. These warnings are acknowledged upstream and do not
# impact functionality or test coverage.
warnings.filterwarnings(
    "ignore",
    message="jsonschema.exceptions.RefResolutionError is deprecated",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message="jsonschema.RefResolver is deprecated as of v4.18.0",
    category=DeprecationWarning,
)

# Silence SQLAlchemy metadata teardown warnings that are triggered during
# drop_all in tests using in-memory SQLite. These warnings are benign for the
# test suite and would otherwise obscure actionable output.
try:
    from sqlalchemy.exc import SAWarning
except Exception:  # pragma: no cover - SQLAlchemy is always available in tests
    SAWarning = None
else:
    warnings.filterwarnings(
        "ignore",
        message="Can't sort tables for DROP; an unresolvable foreign key dependency exists between tables",
        category=SAWarning,
    )


# Provide a lightweight stub for Celery tasks when optional dependencies are
# unavailable in minimal test environments. Pytest session fixtures attempt to
# patch ``theo.services.api.app.workers.tasks.celery`` during import. Without a
# stub the import chain triggers heavy application wiring (Celery, Redis, etc.)
# which is not needed for unit-level suites.
_WORKERS_TASKS_MODULE = "theo.services.api.app.workers.tasks"


def _resolve_absolute_name(name: str, package: str | None, level: int) -> str:
    """Resolve an import request to its absolute module name."""

    if level == 0:
        return name

    if not package:
        raise ValueError("Relative imports require a package context")

    return importlib.util.resolve_name("." * level + name, package)


def _should_install_workers_stub() -> bool:
    """Determine if the Celery stub should be installed."""

    override = os.environ.get("THEORIA_FORCE_WORKER_TASKS_STUB")
    if override is not None:
        return override.lower() not in {"0", "false", "no", ""}

    # When Celery is unavailable the import would fail; pre-install the stub.
    return importlib.util.find_spec("celery") is None


def _install_workers_stub() -> None:
    """Register a lightweight Celery stub to satisfy test imports."""

    workers_pkg = importlib.import_module("theo.services.api.app.workers")

    class _CeleryConfStub:
        def __init__(self) -> None:
            self.task_always_eager = False
            self.task_eager_propagates = False
            self.task_ignore_result = False
            self.task_store_eager_result = False
            self.broker_url = None
            self.result_backend = None

        def update(self, **kwargs: object) -> None:  # pragma: no cover - trivial
            for key, value in kwargs.items():
                setattr(self, key, value)

    class _CeleryStub:
        def __init__(self) -> None:
            self.conf = _CeleryConfStub()

        def task(self, *args: object, **kwargs: object):  # pragma: no cover - defensive
            if args and callable(args[0]) and not kwargs:
                return args[0]

            def decorator(func: types.FunctionType) -> types.FunctionType:
                return func

            return decorator

        def send_task(self, *args: object, **kwargs: object) -> None:  # pragma: no cover
            raise RuntimeError("Celery stub cannot send tasks")

    stub_module = types.ModuleType(_WORKERS_TASKS_MODULE)
    stub_module.celery = _CeleryStub()  # type: ignore[attr-defined]
    sys.modules[_WORKERS_TASKS_MODULE] = stub_module
    setattr(workers_pkg, "tasks", stub_module)


def _register_workers_import_fallback() -> None:
    """Install an import hook to lazily fall back to the Celery stub."""

    if getattr(_register_workers_import_fallback, "_installed", False):
        return

    import builtins

    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ):
        package = None
        if globals:
            package = globals.get("__package__") or globals.get("__name__")

        try:
            return original_import(name, globals, locals, fromlist, level)
        except ImportError as exc:
            try:
                absolute = _resolve_absolute_name(name, package, level)
            except ValueError:
                raise exc

            if absolute != _WORKERS_TASKS_MODULE or _WORKERS_TASKS_MODULE in sys.modules:
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
