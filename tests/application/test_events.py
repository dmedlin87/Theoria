from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from theo.application.ports.events import (
    CompositeEventPublisher,
    DomainEvent,
    EventDispatchError,
    normalise_event_value,
)


def test_domain_event_to_message_serialises_complex_types() -> None:
    event = DomainEvent(
        type="example.created",
        payload={
            "path": Path("/tmp/example.txt"),
            "timestamp": datetime(2024, 1, 1, tzinfo=UTC),
            "tags": {"alpha", "beta"},
        },
        metadata={"attempt": 1},
    )

    message = event.to_message()

    assert message["type"] == "example.created"
    assert message["payload"]["path"] == "/tmp/example.txt"
    assert message["payload"]["timestamp"] == "2024-01-01T00:00:00+00:00"
    assert sorted(message["payload"]["tags"]) == ["alpha", "beta"]
    assert message["metadata"] == {"attempt": 1}
    assert message["occurred_at"].endswith("+00:00")


def test_composite_event_publisher_aggregates_failures() -> None:
    published: list[DomainEvent] = []

    class _OkPublisher:
        def publish(self, event: DomainEvent) -> None:
            published.append(event)

    class _BrokenPublisher:
        def publish(self, event: DomainEvent) -> None:
            raise RuntimeError("boom")

    publisher = CompositeEventPublisher((_OkPublisher(), _BrokenPublisher()))
    event = DomainEvent(type="unit.tested", payload={})

    with pytest.raises(EventDispatchError) as exc_info:
        publisher.publish(event)

    assert exc_info.value.event is event
    assert len(exc_info.value.failures) == 1
    assert published == [event]


def test_normalise_event_value_handles_nested_values() -> None:
    payload = {
        "path": Path("/tmp/example.txt"),
        "when": datetime(2024, 5, 1, 12, 0, tzinfo=UTC),
        "nested": {"values": [1, 2, {"now": datetime(2024, 5, 1, 12, 1, tzinfo=UTC)}]},
    }

    normalised = normalise_event_value(payload)

    assert normalised["path"] == "/tmp/example.txt"
    assert normalised["when"] == "2024-05-01T12:00:00+00:00"
    assert normalised["nested"]["values"][2]["now"] == "2024-05-01T12:01:00+00:00"
