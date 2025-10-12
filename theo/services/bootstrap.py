"""Service-layer bootstrap helpers bridging to the application container."""
from __future__ import annotations

from functools import lru_cache
from typing import Tuple

from theo.adapters import AdapterRegistry
from theo.application import ApplicationContainer
from theo.application.facades.database import get_engine
from theo.application.facades.settings import get_settings
from theo.platform import bootstrap_application


def _noop_command(*_args, **_kwargs):  # pragma: no cover - transitional shim
    return None


def _noop_retire(*_args, **_kwargs) -> None:  # pragma: no cover - transitional shim
    return None


def _noop_get(*_args, **_kwargs):  # pragma: no cover - transitional shim
    return None


def _noop_list(*_args, **_kwargs):  # pragma: no cover - transitional shim
    return []


@lru_cache(maxsize=1)
def resolve_application() -> Tuple[ApplicationContainer, AdapterRegistry]:
    """Initialise the application container and adapter registry."""

    registry = AdapterRegistry()
    registry.register("settings", get_settings)
    registry.register("engine", get_engine)

    container = bootstrap_application(
        registry=registry,
        command_factory=lambda: _noop_command,
        retire_factory=lambda: _noop_retire,
        get_factory=lambda: _noop_get,
        list_factory=lambda: _noop_list,
    )
    return container, registry
