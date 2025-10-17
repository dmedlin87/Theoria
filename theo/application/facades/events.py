"""Event publisher accessors for application services."""
from __future__ import annotations

import logging
from functools import lru_cache

from theo.adapters.events import build_event_publisher
from theo.application.ports.events import (
    CompositeEventPublisher,
    EventPublisher,
    NullEventPublisher,
)

from .settings import Settings, get_settings

LOGGER = logging.getLogger(__name__)


def _build_publishers(settings: Settings) -> list[EventPublisher]:
    publishers: list[EventPublisher] = []
    for sink in settings.event_sinks:
        if getattr(sink, "enabled", True) is False:
            continue
        try:
            publisher = build_event_publisher(sink, settings=settings)
        except Exception:  # pragma: no cover - configuration errors logged and skipped
            sink_name = getattr(sink, "name", None) or getattr(sink, "backend", "unknown")
            LOGGER.exception("Failed to configure event sink %s", sink_name)
            continue
        publishers.append(publisher)
    return publishers


@lru_cache(maxsize=1)
def _get_cached_publisher() -> EventPublisher:
    settings = get_settings()
    publishers = _build_publishers(settings)
    if not publishers:
        return NullEventPublisher()
    if len(publishers) == 1:
        return publishers[0]
    return CompositeEventPublisher(tuple(publishers))


def get_event_publisher(settings: Settings | None = None) -> EventPublisher:
    """Return the configured event publisher instance."""

    if settings is not None:
        publishers = _build_publishers(settings)
        if not publishers:
            return NullEventPublisher()
        if len(publishers) == 1:
            return publishers[0]
        return CompositeEventPublisher(tuple(publishers))
    return _get_cached_publisher()


def reset_event_publisher_cache() -> None:
    """Clear the cached publisher to force reinitialisation."""

    _get_cached_publisher.cache_clear()


__all__ = ["get_event_publisher", "reset_event_publisher_cache"]
