"""Kafka-backed event publisher."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from theo.application.facades.settings import KafkaEventSink
from theo.application.ports.events import DomainEvent, EventPublisher

LOGGER = logging.getLogger(__name__)


class KafkaEventPublisher(EventPublisher):
    """Publish events to Kafka topics."""

    def __init__(
        self,
        config: KafkaEventSink,
        *,
        producer_factory: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        if not config.topic:
            raise ValueError("Kafka event sink requires a topic")
        if not config.bootstrap_servers:
            raise ValueError("Kafka event sink requires bootstrap_servers")

        if producer_factory is None:  # pragma: no cover - exercised in integration
            try:
                from confluent_kafka import Producer  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "Kafka support requires the 'confluent-kafka' package"
                ) from exc

            def producer_factory(options: dict[str, Any]) -> Any:
                return Producer(options)

        options = {"bootstrap.servers": config.bootstrap_servers}
        options.update(config.producer_config)
        self._producer = producer_factory(options)
        self._topic = config.topic
        self._flush_timeout = config.flush_timeout_seconds

    def publish(self, event: DomainEvent) -> None:
        message = json.dumps(event.to_message(), ensure_ascii=False, separators=(",", ":"))
        headers = None
        if event.headers:
            headers = [
                (str(key), str(value).encode("utf-8"))
                for key, value in event.headers.items()
            ]
        try:
            self._producer.produce(
                topic=self._topic,
                value=message.encode("utf-8"),
                key=event.key,
                headers=headers,
            )
            self._producer.poll(0)
            if self._flush_timeout is not None:
                self._producer.flush(self._flush_timeout)
        except Exception as exc:  # pragma: no cover - logging for observability
            LOGGER.exception("Failed to publish Kafka event")
            raise


__all__ = ["KafkaEventPublisher"]
