from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from theo.adapters.events import build_event_publisher
from theo.adapters.events.kafka import KafkaEventPublisher
from theo.adapters.events.redis import RedisStreamEventPublisher
from theo.application.facades.settings import KafkaEventSink, RedisStreamEventSink
from theo.application.ports.events import DomainEvent


def test_kafka_event_publisher_uses_factory() -> None:
    sink = KafkaEventSink(
        topic="theo.events",
        bootstrap_servers="kafka:9092",
        producer_config={"acks": "all"},
    )

    created: dict[str, object] = {}

    class _Producer:
        def __init__(self, config: dict[str, object]) -> None:
            self.config = config
            self.calls: list[dict[str, object]] = []
            self.polls: list[int | float] = []
            self.flushes: list[int | float] = []

        def produce(self, *, topic: str, value: bytes, key=None, headers=None) -> None:
            self.calls.append(
                {
                    "topic": topic,
                    "value": value,
                    "key": key,
                    "headers": headers,
                }
            )

        def poll(self, timeout: float) -> None:
            self.polls.append(timeout)

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    def _factory(config: dict[str, object]) -> _Producer:
        created["config"] = config
        producer = _Producer(config)
        created["producer"] = producer
        return producer

    publisher = KafkaEventPublisher(sink, producer_factory=_factory)
    event = DomainEvent(type="theo.example", payload={"id": "123"}, key="123")

    publisher.publish(event)

    producer = created["producer"]
    assert created["config"] == {
        "bootstrap.servers": "kafka:9092",
        "acks": "all",
    }
    assert len(producer.calls) == 1
    call = producer.calls[0]
    assert call["topic"] == "theo.events"
    assert call["key"] == "123"
    payload = json.loads(call["value"].decode("utf-8"))
    assert payload["type"] == "theo.example"
    assert payload["payload"] == {"id": "123"}
    assert producer.polls == [0]
    assert producer.flushes == [sink.flush_timeout_seconds]


def test_kafka_event_publisher_batches_with_flush_timeout() -> None:
    sink = KafkaEventSink(
        topic="batched",
        bootstrap_servers="kafka:9092",
        producer_config={},
        flush_timeout_seconds=0.5,
    )

    class _Producer:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []
            self.polls: list[float] = []
            self.flushes: list[float] = []

        def produce(self, *, topic: str, value: bytes, key=None, headers=None) -> None:
            self.calls.append(
                {
                    "topic": topic,
                    "value": value,
                    "key": key,
                    "headers": headers,
                }
            )

        def poll(self, timeout: float) -> None:
            self.polls.append(timeout)

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    producer = _Producer()

    def factory(options: dict[str, object]) -> _Producer:
        return producer

    publisher = KafkaEventPublisher(
        sink,
        producer_factory=factory,
        batch_size=3,
        flush_interval_seconds=60.0,
    )

    event = DomainEvent(type="batched", payload={"id": "1"})

    publisher.publish(event)
    assert producer.flushes == [sink.flush_timeout_seconds]

    publisher.publish(event)
    assert producer.flushes == [sink.flush_timeout_seconds]

    publisher.publish(event)
    assert producer.flushes == [sink.flush_timeout_seconds, sink.flush_timeout_seconds]


def test_redis_stream_event_publisher_appends_messages() -> None:
    sink = RedisStreamEventSink(stream="events", redis_url="redis://redis:6379/0", maxlen=100)

    class _Client:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

        def xadd(self, stream: str, fields: dict[str, str], **kwargs: object) -> str:
            self.calls.append((stream, fields, kwargs))
            return "0-0"

    client = _Client()
    publisher = RedisStreamEventPublisher(sink, redis_client=client)
    event = DomainEvent(type="theo.example", payload={"id": "abc"})

    publisher.publish(event)

    assert len(client.calls) == 1
    stream, fields, kwargs = client.calls[0]
    assert stream == "events"
    assert json.loads(fields["body"]) == event.to_message()
    assert kwargs == {"maxlen": 100, "approximate": True}


def test_build_event_publisher_resolves_sink_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = RedisStreamEventSink(stream="events", redis_url=None)
    settings = SimpleNamespace(redis_url="redis://redis:6379/1")
    constructed: dict[str, RedisStreamEventSink] = {}

    class _StubPublisher:
        def __init__(self, config: RedisStreamEventSink) -> None:
            constructed["config"] = config

        def publish(self, event: DomainEvent) -> None:  # pragma: no cover - stub
            pass

    monkeypatch.setattr("theo.adapters.events.RedisStreamEventPublisher", _StubPublisher)

    publisher = build_event_publisher(sink, settings=settings)  # type: ignore[arg-type]

    assert isinstance(publisher, _StubPublisher)
    assert constructed["config"].redis_url == settings.redis_url


def test_kafka_event_publisher_propagates_producer_errors() -> None:
    sink = KafkaEventSink(topic="failures", bootstrap_servers="kafka:9092", producer_config={})

    class _Producer:
        def __init__(self) -> None:
            self.polls: list[float] = []
            self.flushes: list[float] = []

        def produce(self, **kwargs: object) -> None:  # noqa: ANN001 - mimic confluent producer signature
            raise RuntimeError("produce failed")

        def poll(self, timeout: float) -> None:
            self.polls.append(timeout)

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    created: dict[str, _Producer] = {}

    def factory(options: dict[str, object]) -> _Producer:
        producer = _Producer()
        created["producer"] = producer
        return producer

    publisher = KafkaEventPublisher(sink, producer_factory=factory)
    event = DomainEvent(type="failure", payload={})

    with pytest.raises(RuntimeError):
        publisher.publish(event)

    producer = created["producer"]
    assert producer.polls == []
    assert producer.flushes == []


def test_redis_stream_event_publisher_propagates_client_errors() -> None:
    sink = RedisStreamEventSink(stream="events", redis_url="redis://redis:6379/0")

    class _Client:
        def xadd(self, *args, **kwargs):  # noqa: ANN001 - mimic redis client signature
            raise RuntimeError("redis failure")

    publisher = RedisStreamEventPublisher(sink, redis_client=_Client())
    event = DomainEvent(type="redis", payload={})

    with pytest.raises(RuntimeError):
        publisher.publish(event)


def test_redis_stream_event_publisher_uses_client_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = RedisStreamEventSink(stream="events", redis_url="redis://custom:6379/0", maxlen=50)
    captured: dict[str, object] = {}

    class _Client:
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def xadd(self, *args: object, **kwargs: object) -> str:
            self.calls.append((args, kwargs))
            return "0-1"

    def factory(url: str) -> _Client:
        captured["url"] = url
        client = _Client()
        captured["client"] = client
        return client

    publisher = RedisStreamEventPublisher(sink, client_factory=factory)
    event = DomainEvent(type="redis", payload={"id": 1})

    publisher.publish(event)

    assert captured["url"] == "redis://custom:6379/0"
    client: _Client = captured["client"]  # type: ignore[assignment]
    assert len(client.calls) == 1
    args, kwargs = client.calls[0]
    assert args[0] == "events"
    assert kwargs == {"maxlen": 50, "approximate": True}
