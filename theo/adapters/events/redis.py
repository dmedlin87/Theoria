"""Redis Streams event publisher."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from theo.application.facades.settings import RedisStreamEventSink
from theo.application.ports.events import DomainEvent, EventPublisher

LOGGER = logging.getLogger(__name__)


class RedisStreamEventPublisher(EventPublisher):
    """Publish events to a Redis Stream."""

    def __init__(
        self,
        config: RedisStreamEventSink,
        *,
        redis_client: Any | None = None,
        client_factory: Callable[[str], Any] | None = None,
    ) -> None:
        if not config.stream:
            raise ValueError("Redis stream event sink requires a stream name")
        if redis_client is None:
            if config.redis_url is None:
                raise ValueError("Redis stream event sink requires a redis_url")
            if client_factory is None:  # pragma: no cover - exercised in integration
                try:
                    import redis  # type: ignore
                except ImportError as exc:  # pragma: no cover - optional dependency
                    raise RuntimeError(
                        "Redis stream support requires the 'redis' package"
                    ) from exc

                def client_factory(url: str) -> Any:
                    return redis.Redis.from_url(url, decode_responses=True)
            redis_client = client_factory(config.redis_url)
        self._client = redis_client
        self._stream = config.stream
        self._maxlen = config.maxlen
        self._approximate = config.approximate_trim

    def publish(self, event: DomainEvent) -> None:
        message = json.dumps(event.to_message(), ensure_ascii=False, separators=(",", ":"))
        arguments: dict[str, Any] = {"body": message}
        kwargs: dict[str, Any] = {}
        if self._maxlen is not None:
            kwargs["maxlen"] = self._maxlen
            kwargs["approximate"] = self._approximate
        try:
            self._client.xadd(self._stream, arguments, **kwargs)
        except Exception as exc:  # pragma: no cover - logging for observability
            LOGGER.exception("Failed to append event to Redis stream", exc_info=exc)
            raise


__all__ = ["RedisStreamEventPublisher"]
