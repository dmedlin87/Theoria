from __future__ import annotations

import asyncio
import logging

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


def test_event_bus_unsubscribe_removes_handler() -> None:
    bus = EventBus()
    calls: list[str] = []

    def handler(event: _DummyEvent) -> None:
        calls.append("handled")

    bus.subscribe(_DummyEvent, handler)
    bus.unsubscribe(_DummyEvent, handler)

    bus.publish(_DummyEvent())

    assert calls == []


def test_event_bus_logs_errors_and_continues(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus()
    caplog.set_level(logging.ERROR, logger="theo.platform.events")

    def bad_handler(event: _DummyEvent) -> None:
        raise RuntimeError("boom")

    def good_handler(event: _DummyEvent) -> str:
        return "ok"

    bus.subscribe(_DummyEvent, bad_handler)
    bus.subscribe(_DummyEvent, good_handler)

    results = bus.publish(_DummyEvent())

    assert results == ["ok"]
    assert any("event handler failed" in record.getMessage() for record in caplog.records)


def test_event_bus_requires_event_or_key() -> None:
    bus = EventBus()

    with pytest.raises(ValueError):
        bus.publish(None)


def test_event_bus_async_dispatch_outside_loop() -> None:
    bus = EventBus()
    bus.subscribe("health", lambda event: "ready")

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        future = bus.publish("ignored", key="health", async_dispatch=True)
        results = loop.run_until_complete(future)
    finally:
        asyncio.set_event_loop(None)
        loop.close()

    assert results == ["ready"]
