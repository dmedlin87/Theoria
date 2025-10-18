"""Helpers for isolating the Theo application container in tests."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Callable, Tuple, TypeVar, overload

from theo.adapters import AdapterRegistry
from theo.application import ApplicationContainer
from theo.platform.application import resolve_application as _resolve_application

FactoryValue = TypeVar("FactoryValue")
FactoryOverride = Callable[[], FactoryValue] | FactoryValue


def _normalise_factory(value: FactoryOverride[FactoryValue]) -> Callable[[], FactoryValue]:
    if callable(value):
        factory = value  # type: ignore[assignment]
        return factory
    return lambda: value  # type: ignore[arg-type]


@overload
@contextmanager
def isolated_application_container(
    overrides: Mapping[str, FactoryOverride[object]] | None = ...,
) -> Iterator[Tuple[ApplicationContainer, AdapterRegistry]]:
    ...


@contextmanager
def isolated_application_container(
    overrides: Mapping[str, FactoryOverride[object]] | None = None,
) -> Iterator[Tuple[ApplicationContainer, AdapterRegistry]]:
    """Yield a freshly initialised application container and registry."""

    _resolve_application.cache_clear()
    container, registry = _resolve_application()

    original_factories = dict(registry.factories)
    if overrides:
        for port, factory in overrides.items():
            registry.factories[port] = _normalise_factory(factory)

    try:
        yield container, registry
    finally:
        registry.factories.clear()
        registry.factories.update(original_factories)
        _resolve_application.cache_clear()

