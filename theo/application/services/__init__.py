"""Application-layer service helpers and orchestration utilities."""
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from .container import ApplicationContainer as ApplicationContainer

__all__ = ["ApplicationContainer", "resolve_application"]


def __getattr__(name: str):
    if name == "ApplicationContainer":
        module = import_module("theo.application.services.container")
        value = getattr(module, "ApplicationContainer")
        globals()[name] = value
        return value
    if name == "resolve_application":
        from .bootstrap import resolve_application as _resolve_application

        globals()[name] = _resolve_application
        return _resolve_application
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
