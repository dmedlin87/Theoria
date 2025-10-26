from __future__ import annotations

import importlib
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
