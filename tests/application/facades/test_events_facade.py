"""Tests for the events facade helpers."""

from __future__ import annotations

import pytest

from theo.application.facades import events as events_module
from theo.application.facades.events import get_event_publisher, reset_event_publisher_cache
from theo.application.facades.settings import KafkaEventSink, RedisStreamEventSink, Settings
from theo.application.ports.events import CompositeEventPublisher, NullEventPublisher


@pytest.fixture(autouse=True)
def _reset_event_publisher_cache() -> None:
    """Ensure the cached publisher state does not leak between tests."""

    reset_event_publisher_cache()
    yield
    reset_event_publisher_cache()


def _settings_with_sinks(*sinks: KafkaEventSink | RedisStreamEventSink) -> Settings:
    """Return a ``Settings`` instance containing the provided sinks."""

    return Settings(event_sinks=list(sinks))


def test_get_event_publisher_returns_null_for_empty_configuration() -> None:
    settings = _settings_with_sinks()

    publisher = get_event_publisher(settings)

    assert isinstance(publisher, NullEventPublisher)


def test_get_event_publisher_returns_single_configured_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = KafkaEventSink(name="primary", topic="theoria", bootstrap_servers="localhost:9092")
    settings = _settings_with_sinks(sink)
    created_publishers: list[object] = []

    def fake_builder(config: object, *, settings: Settings) -> object:
        assert config is sink
        assert settings is settings_obj
        publisher = object()
        created_publishers.append(publisher)
        return publisher

    settings_obj = settings
    monkeypatch.setattr(events_module, "build_event_publisher", fake_builder)

    publisher = get_event_publisher(settings_obj)

    assert publisher is created_publishers[0]


def test_get_event_publisher_composes_multiple_sinks(monkeypatch: pytest.MonkeyPatch) -> None:
    kafka_sink = KafkaEventSink(name="kafka", topic="theoria", bootstrap_servers="localhost:9092")
    redis_sink = RedisStreamEventSink(name="redis", stream="theoria", redis_url="redis://example")
    settings = _settings_with_sinks(kafka_sink, redis_sink)
    publisher_mapping: dict[int, object] = {}

    def fake_builder(config: object, *, settings: Settings) -> object:
        assert settings is settings_obj
        key = id(config)
        publisher = publisher_mapping.setdefault(key, object())
        return publisher

    settings_obj = settings
    monkeypatch.setattr(events_module, "build_event_publisher", fake_builder)

    publisher = get_event_publisher(settings_obj)

    assert isinstance(publisher, CompositeEventPublisher)
    assert publisher.publishers == (
        publisher_mapping[id(kafka_sink)],
        publisher_mapping[id(redis_sink)],
    )


def test_get_event_publisher_uses_cached_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = KafkaEventSink(name="cached", topic="theoria", bootstrap_servers="localhost:9092")
    settings = _settings_with_sinks(sink)
    constructed: list[object] = []

    def fake_builder(config: object, *, settings: Settings) -> object:
        assert config is sink
        assert settings is settings_obj
        publisher = object()
        constructed.append(publisher)
        return publisher

    settings_obj = settings
    monkeypatch.setattr(events_module, "build_event_publisher", fake_builder)
    monkeypatch.setattr(events_module, "get_settings", lambda: settings_obj)

    first = get_event_publisher()
    second = get_event_publisher()

    assert first is second
    assert constructed == [first]

    reset_event_publisher_cache()
    third = get_event_publisher()

    assert third is not first
    assert constructed == [first, third]
