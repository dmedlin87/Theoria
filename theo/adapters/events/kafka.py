"""Kafka-backed event publisher."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable

from theo.application.facades.settings import KafkaEventSink
from theo.application.ports.events import DomainEvent, EventPublisher

LOGGER = logging.getLogger(__name__)


class KafkaEventPublisher(EventPublisher):
    """Publish events to Kafka topics with batching support."""

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
        
        # Batching configuration
        self._batch_size = max(1, config.batch_size)
        self._flush_interval = max(0.1, config.flush_interval_seconds)
        
        # State for batching
        self._message_count = 0
        self._last_flush = time.time()
        self._lock = threading.Lock()
        self._closed = False

    def publish(self, event: DomainEvent) -> None:
        """Publish event with intelligent batching."""
        if self._closed:
            raise RuntimeError("Publisher is closed")
            
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
            self._producer.poll(0)  # Non-blocking poll for callbacks
            
            # Intelligent flushing logic
            with self._lock:
                self._message_count += 1
                current_time = time.time()
                time_since_flush = current_time - self._last_flush

                should_flush = (
                    self._message_count >= self._batch_size or
                    time_since_flush >= self._flush_interval
                )

                if should_flush:
                    timeout = self._flush_timeout if self._flush_timeout is not None else 30.0
                    self._producer.flush(timeout)
                    self._message_count = 0
                    self._last_flush = current_time
                elif self._flush_timeout is not None:
                    # Preserve legacy synchronous semantics for single publishes so callers
                    # relying on flush_timeout continue to have their messages delivered
                    # immediately, even when batching would otherwise defer the flush.
                    self._producer.flush(self._flush_timeout)
                    self._message_count = 0
                    self._last_flush = current_time
                    
        except Exception as exc:  # pragma: no cover - logging for observability
            LOGGER.exception("Failed to publish Kafka event")
            raise

    def flush(self) -> None:
        """Explicitly flush all pending messages."""
        if self._closed:
            return
            
        try:
            timeout = self._flush_timeout if self._flush_timeout is not None else 30.0
            self._producer.flush(timeout)
            with self._lock:
                self._message_count = 0
                self._last_flush = time.time()
        except Exception as exc:
            LOGGER.warning("Failed to flush Kafka producer: %s", exc)
            
    def close(self) -> None:
        """Close the publisher and flush remaining messages."""
        if self._closed:
            return
            
        self._closed = True
        try:
            # Final flush with longer timeout
            timeout = max(30.0, self._flush_timeout or 30.0)
            self._producer.flush(timeout)
        except Exception as exc:
            LOGGER.warning("Failed to flush on close: %s", exc)

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


__all__ = ["KafkaEventPublisher"]
