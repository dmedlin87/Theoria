from __future__ import annotations

from collections.abc import Sequence

import pytest

from theo.infrastructure.api.app.ingest.embeddings import EmbeddingService


def _stubbed_encode_factory(
    service: EmbeddingService, calls: list[Sequence[str]]
):  # pragma: no cover - helper
    def _encode(texts: Sequence[str]) -> list[list[float]]:
        calls.append(tuple(texts))
        return [[1.0] + [0.0] * (service.dimension - 1) for _ in texts]

    return _encode


def test_embed_reuses_cached_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EmbeddingService("stub", 4, cache_max_size=8)
    calls: list[Sequence[str]] = []
    monkeypatch.setattr(service, "_encode", _stubbed_encode_factory(service, calls))

    first = service.embed(["alpha", "beta"])
    second = service.embed(["alpha", "beta"])

    assert len(calls) == 1
    assert second == first


def test_embed_deduplicates_within_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EmbeddingService("stub", 3, cache_max_size=8)
    calls: list[Sequence[str]] = []
    monkeypatch.setattr(service, "_encode", _stubbed_encode_factory(service, calls))

    vectors = service.embed(["repeat", "repeat", "unique"])
    assert len(calls) == 1
    assert calls[0] == ("repeat", "unique")
    assert vectors[0] == vectors[1]

    service.embed(["repeat"])
    assert len(calls) == 1

    service.clear_cache()
    service.embed(["repeat"])
    assert len(calls) == 2


def test_embed_lru_eviction(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EmbeddingService("stub", 3, cache_max_size=2)
    calls: list[Sequence[str]] = []
    monkeypatch.setattr(service, "_encode", _stubbed_encode_factory(service, calls))

    service.embed(["alpha", "beta"])
    service.embed(["gamma"])

    assert calls == [("alpha", "beta"), ("gamma",)]

    service.embed(["alpha"])
    assert calls == [("alpha", "beta"), ("gamma",), ("alpha",)]

    service.embed(["gamma"])
    assert calls == [("alpha", "beta"), ("gamma",), ("alpha",)]
