from __future__ import annotations

from collections import OrderedDict
from typing import Iterable, Sequence

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from theo.services.api.app.ingest.embeddings import (
    EmbeddingService,
    ResilienceError,
    lexical_representation,
)
from theo.services.api.app.resilience import ResilienceMetadata

import theo.services.api.app.ingest.embeddings as embeddings_module


class _RecordingEncoder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        captured = tuple(texts)
        self.calls.append(captured)
        return [[float(len(text)) for _ in range(3)] for text in texts]


def _service(cache_max_size: int | None = 16) -> EmbeddingService:
    service = EmbeddingService("test", dimension=3, cache_max_size=cache_max_size)
    return service


def test_embedding_service_caches_unique_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    encoder = _RecordingEncoder()

    def fake_encode(self: EmbeddingService, texts: Sequence[str]) -> list[list[float]]:
        return encoder.encode(texts)

    service = _service()
    monkeypatch.setattr(EmbeddingService, "_encode", fake_encode, raising=False)

    vectors = service.embed(["alpha", "beta", "alpha"], batch_size=2)

    assert len(vectors) == 3
    assert encoder.calls == [("alpha", "beta")]

    service.embed(["beta", "gamma"])

    assert encoder.calls == [("alpha", "beta"), ("gamma",)]


def test_embedding_service_respects_cache_max_size(monkeypatch: pytest.MonkeyPatch) -> None:
    encoder = _RecordingEncoder()

    service = _service(cache_max_size=1)

    def fake_encode(self: EmbeddingService, texts: Sequence[str]) -> list[list[float]]:
        return encoder.encode(texts)

    monkeypatch.setattr(EmbeddingService, "_encode", fake_encode, raising=False)

    service.embed(["alpha"])
    assert list(service._cache.keys()) == ["alpha"]

    service.embed(["beta"])
    assert list(service._cache.keys()) == ["beta"]

    service.embed(["alpha"])
    assert encoder.calls == [("alpha",), ("beta",), ("alpha",)]


def test_embedding_service_clear_cache() -> None:
    service = _service(cache_max_size=2)
    service._cache = OrderedDict({"alpha": (1.0, 2.0, 3.0)})

    service.clear_cache()

    assert service._cache == OrderedDict()


def test_embedding_service_records_span_on_resilience_error(monkeypatch: pytest.MonkeyPatch) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    tracer = provider.get_tracer("theo.embedding")
    monkeypatch.setattr(embeddings_module, "_TRACER", tracer)

    metadata = ResilienceMetadata(
        attempts=2,
        category="timeout",
        circuit_open=False,
        last_exception="boom",
        duration=0.5,
        classification="embedding",
        policy={"max_attempts": 2},
    )

    def fail_encode(self: EmbeddingService, texts: Sequence[str]) -> list[list[float]]:
        raise ResilienceError("failed", metadata)

    service = _service()
    monkeypatch.setattr(EmbeddingService, "_encode", fail_encode, raising=False)

    with pytest.raises(ResilienceError):
        service.embed(["alpha"])

    spans = exporter.get_finished_spans()
    assert spans
    span = spans[-1]
    assert span.attributes["embedding.resilience_category"] == "timeout"
    assert span.attributes["embedding.resilience_attempts"] == 2


class _FakeDialect:
    name = "postgresql"


class _FakeBind:
    dialect = _FakeDialect()


class _FakeSession:
    bind = _FakeBind()


def test_lexical_representation_uses_ts_vector() -> None:
    clause = lexical_representation(_FakeSession(), "In the beginning")
    compiled = str(clause)
    assert "to_tsvector" in compiled
    args = list(clause.clauses)
    assert any(getattr(arg, "value", None) == "english" for arg in args)
    assert any(getattr(arg, "value", None) == "In the beginning" for arg in args)


def test_lexical_representation_sqlite_fallback() -> None:
    clause = lexical_representation(object(), "In the beginning God created")

    assert clause == "in the beginning god created"
