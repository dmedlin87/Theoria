"""Reusable factories and seeded fixtures for regression tests.

This module re-exports factories backed by optional dependencies.  The
architecture tests only need the module to import cleanly; however, the
regression fixtures rely on ``pydantic`` and other heavy packages.  When
those dependencies are not available (for example in the lightweight
execution environment used for the architecture checks) importing the
fixtures would raise ``ModuleNotFoundError`` and prevent ``pytest`` from
collecting the tests altogether.

To keep the ergonomics for full regression runs while allowing lighter
test selections, we lazily expose placeholders that fail with a clear
message if the optional dependencies are missing.  This mirrors the
behaviour of the fixtures themselves, which skip when their requirements
are not installed, and unblocks the architecture suites from importing the
module hierarchy.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


def _missing_dependency_factory(exc: ModuleNotFoundError) -> Callable[..., Any]:
    """Return a callable that re-raises a helpful error message."""

    def _raiser(*_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover - error path
        raise ModuleNotFoundError(
            "Optional regression fixture dependencies are not installed. "
            "Install the 'regression' extras or set THEORIA_SKIP_HEAVY_FIXTURES=1 "
            "to skip loading them."
        ) from exc

    return _raiser


REGRESSION_IMPORT_ERROR: Optional[ModuleNotFoundError] = None
REGRESSION_FIXTURES_AVAILABLE = True


try:  # pragma: no cover - exercised in environments with full deps
    from .regression_factory import (  # type: ignore
        DocumentRecord,
        PassageRecord,
        RegressionDataFactory,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - triggered in lightweight envs
    if exc.name == "pydantic":
        REGRESSION_FIXTURES_AVAILABLE = False
        REGRESSION_IMPORT_ERROR = exc
        DocumentRecord = _missing_dependency_factory(exc)  # type: ignore[assignment]
        PassageRecord = _missing_dependency_factory(exc)  # type: ignore[assignment]
        RegressionDataFactory = _missing_dependency_factory(exc)  # type: ignore[assignment]
    else:  # pragma: no cover - unexpected import error
        raise
else:
    REGRESSION_IMPORT_ERROR = None


__all__ = [
    "DocumentRecord",
    "PassageRecord",
    "RegressionDataFactory",
    "REGRESSION_FIXTURES_AVAILABLE",
    "REGRESSION_IMPORT_ERROR",
]
