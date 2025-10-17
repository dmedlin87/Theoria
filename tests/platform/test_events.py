from __future__ import annotations

import asyncio

import pytest

from theo.platform.events import EventBus


class _DummyEvent:
    pass


def test_event_bus_dispatches_in_registration_order() -> None:
    bus = EventBus()
    order: list[str] = []

    def handler_one(event: _DummyEvent) -> str:
        order.append("one")
        return "first"

    def handler_two(event: _DummyEvent) -> str:
        order.append("two")
        return "second"

    bus.subscribe(_DummyEvent, handler_one)
    bus.subscribe(_DummyEvent, handler_two)

    results = bus.publish(_DummyEvent())

    assert results == ["first", "second"]
    assert order == ["one", "two"]


@pytest.mark.asyncio
async def test_event_bus_async_dispatch_handles_coroutines() -> None:
    bus = EventBus()
    events: list[str] = []

    async def async_handler(event: _DummyEvent) -> str:
        await asyncio.sleep(0)
        events.append("async")
        return "async-result"

    def sync_handler(event: _DummyEvent) -> str:
        events.append("sync")
        return "sync-result"

    bus.subscribe(_DummyEvent, async_handler)
    bus.subscribe(_DummyEvent, sync_handler)

    results = await bus.publish_async(_DummyEvent())

    assert results == ["async-result", "sync-result"]
    assert events == ["async", "sync"]
