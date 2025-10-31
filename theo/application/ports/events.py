"""Domain event publishing contracts."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Protocol, Sequence


_LOGGER = logging.getLogger(__name__)


class EventPublisher(Protocol):
    """Port definition for infrastructure responsible for emitting events."""

    def publish(self, event: "DomainEvent") -> None:
        """Persist *event* to the configured sink."""


@dataclass(slots=True)
class DomainEvent:
    """Envelope describing a domain event."""

    type: str
    payload: Mapping[str, Any]
    key: str | None = None
    metadata: Mapping[str, Any] | None = None
    headers: Mapping[str, str] | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_message(self) -> MutableMapping[str, Any]:
        """Return a serialisable representation of the event."""

        body: MutableMapping[str, Any] = {
            "type": self.type,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": normalise_event_value(self.payload),
        }
        if self.metadata:
            body["metadata"] = normalise_event_value(self.metadata)
        return body


class EventDispatchError(RuntimeError):
    """Raised when one or more event sinks fail."""

    def __init__(self, event: DomainEvent, failures: Sequence[Exception]) -> None:
        self.event = event
        self.failures = tuple(failures)
        message = (
            f"Failed to publish event {event.type!r} to {len(self.failures)} sink(s)"
        )
        super().__init__(message)


class NullEventPublisher(EventPublisher):
    """Fallback publisher used when no sinks are configured."""

    def publish(self, event: DomainEvent) -> None:  # noqa: D401 - intentionally noop
        return


@dataclass(slots=True)
class CompositeEventPublisher(EventPublisher):
    """Dispatches events to all configured sinks with configurable error handling.
    
    Supports two modes:
    - fail_fast=True (default): Stop on first failure for consistency
    - fail_fast=False: Attempt all publishers for best-effort delivery
    """

    publishers: Sequence[EventPublisher]
    fail_fast: bool = True

    def publish(self, event: DomainEvent) -> None:
        """Publish event to all publishers with configurable error handling.
        
        Args:
            event: Domain event to publish
            
        Raises:
            EventDispatchError: When publishers fail (immediately if fail_fast=True,
                               after all attempts if fail_fast=False)
        """
        failures: list[Exception] = []
        successful_publishers = 0
        
        for publisher in self.publishers:
            try:
                publisher.publish(event)
                successful_publishers += 1
            except Exception as exc:  # pragma: no cover - defensive logging occurs upstream
                failures.append(exc)
                _LOGGER.warning(
                    "Publisher failed for event %s: %s", 
                    event.type, exc, exc_info=True
                )
                
                if self.fail_fast:
                    # Stop immediately on first failure to ensure consistency
                    raise EventDispatchError(event, failures)
        
        # If we get here and have failures, we're in best-effort mode
        if failures:
            _LOGGER.error(
                "Event %s partially delivered: %d successful, %d failed",
                event.type, successful_publishers, len(failures)
            )
            raise EventDispatchError(event, failures)
        
        # All publishers succeeded
        if successful_publishers > 0:
            _LOGGER.debug(
                "Event %s successfully delivered to %d publisher(s)",
                event.type, successful_publishers
            )


def normalise_event_value(value: Any) -> Any:
    """Convert *value* into a JSON-serialisable structure."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (set, frozenset)):
        return [normalise_event_value(item) for item in sorted(value, key=str)]
    if isinstance(value, Mapping):
        normalised: dict[str, Any] = {}
        for key, item in value.items():
            normalised[str(key)] = normalise_event_value(item)
        return normalised
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [normalise_event_value(item) for item in value]
    return str(value)


__all__ = [
    "CompositeEventPublisher",
    "DomainEvent",
    "EventDispatchError",
    "EventPublisher",
    "NullEventPublisher",
    "normalise_event_value",
]
