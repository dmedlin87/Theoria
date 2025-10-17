"""Infrastructure event publishers."""
from __future__ import annotations

from theo.application.facades.settings import (
    EventSink,
    KafkaEventSink,
    RedisStreamEventSink,
    Settings,
)
from theo.application.ports.events import EventPublisher

from .kafka import KafkaEventPublisher
from .redis import RedisStreamEventPublisher

__all__ = [
    "KafkaEventPublisher",
    "RedisStreamEventPublisher",
    "build_event_publisher",
]


def build_event_publisher(config: EventSink, *, settings: Settings) -> EventPublisher:
    """Return a configured event publisher for *config*."""

    if isinstance(config, KafkaEventSink):
        return KafkaEventPublisher(config)
    if isinstance(config, RedisStreamEventSink):
        redis_config = config
        if redis_config.redis_url is None:
            redis_config = redis_config.model_copy(
                update={"redis_url": settings.redis_url}
            )
        return RedisStreamEventPublisher(redis_config)
    raise TypeError(
        f"Unsupported event sink configuration: {type(config).__name__}"  # pragma: no cover
    )
