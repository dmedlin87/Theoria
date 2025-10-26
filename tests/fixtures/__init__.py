"""Reusable factories and seeded fixtures for regression tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - imported only for type checking
    from .regression_factory import (
        DocumentRecord,
        PassageRecord,
        RegressionDataFactory,
    )

__all__ = ["DocumentRecord", "PassageRecord", "RegressionDataFactory"]


def __getattr__(name: str):  # pragma: no cover - thin convenience shim
    """Lazily import heavy regression fixtures when requested.

    The regression factory pulls in optional third-party dependencies (for
    example :mod:`pydantic` and :mod:`opentelemetry`) that are not required for
    the lightweight worker suites. Importing ``tests.fixtures`` at module import
    time previously caused those optional imports to execute eagerly, raising a
    :class:`ModuleNotFoundError` and preventing unrelated tests from running.

    By deferring the import until the attributes are actually accessed we allow
    lightweight environments to load the package successfully while still
    surfacing a helpful error message when the regression fixtures are used
    without their optional dependencies installed.
    """

    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    try:
        from . import regression_factory
    except ModuleNotFoundError as exc:  # pragma: no cover - optional deps missing
        raise ModuleNotFoundError(
            "Optional dependencies for regression fixtures are not installed. "
            "Install the 'regression' extras or set THEORIA_SKIP_HEAVY_FIXTURES=1 "
            "to skip them."
        ) from exc

    value = getattr(regression_factory, name)
    globals()[name] = value
    return value
