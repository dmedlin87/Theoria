"""Helpers for lazily importing application fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:  # pragma: no cover - imported only for type checking
    from theo.adapters import AdapterRegistry
    from theo.application import ApplicationContainer
    from tests.factories import RegressionDataFactory

__all__ = [
    "isolated_application_container",
    "require_application_factory",
]


try:  # pragma: no cover - factory depends on optional domain extras
    from tests.factories.application import isolated_application_container
except Exception as exc:  # pragma: no cover - light environments
    isolated_application_container = None  # type: ignore[assignment]
    _APPLICATION_FACTORY_IMPORT_ERROR = exc
else:
    _APPLICATION_FACTORY_IMPORT_ERROR: Exception | None = None


def require_application_factory() -> None:
    if isolated_application_container is None:
        reason = _APPLICATION_FACTORY_IMPORT_ERROR or ModuleNotFoundError("pythonbible")
        pytest.skip(f"application factory unavailable: {reason}")
