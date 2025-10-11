from __future__ import annotations

from types import SimpleNamespace

import pytest

from theo.services.api.app.models.search import HybridSearchRequest, HybridSearchResult
from theo.services.api.app.services import retrieval_service as retrieval_module
from theo.services.api.app.services.retrieval_service import RetrievalService


class _StubReranker:
    def __init__(self, ordered_ids: list[str], raise_error: bool = False):
        self._ordered_ids = ordered_ids
        self._raise = raise_error
        self.calls: list[list[HybridSearchResult]] = []

    def rerank(self, results: list[HybridSearchResult]) -> list[HybridSearchResult]:
        if self._raise:
            raise RuntimeError("rerank failure")
        self.calls.append(list(results))
        ordered: list[HybridSearchResult] = []
        lookup = {item.id: item for item in results}
        for identifier in self._ordered_ids:
            ordered.append(lookup[identifier])
        return ordered


class _StubCache:
    def __init__(self, reranker: _StubReranker | None):
        self._reranker = reranker
        self.calls: list[tuple[str | None, str | None]] = []

    def resolve(self, model_path, expected_sha256):  # noqa: ANN001
        self.calls.append((model_path, expected_sha256))
        return self._reranker

    def reset(self) -> None:  # pragma: no cover - compatibility with cache protocol
        self.calls.clear()


def _make_result(identifier: str, score: float) -> HybridSearchResult:
    return HybridSearchResult(
        id=identifier,
        document_id=f"doc-{identifier}",
        text="body",
        snippet="snippet",
        osis_ref=None,
        score=score,
        rank=int(identifier[-1]) if identifier[-1].isdigit() else 0,
    )


def test_search_without_reranker_returns_results() -> None:
    settings = SimpleNamespace(reranker_enabled=False, reranker_model_path=None, reranker_model_sha256=None)
    results = [_make_result("r1", 0.5), _make_result("r2", 0.4)]

    def _search(session, request):  # noqa: ANN001
        return list(results)

    service = RetrievalService(
        settings=settings,
        search_fn=_search,
        reranker_cache=_StubCache(None),
    )

    payload = HybridSearchRequest(query="test")
    resolved, header = service.search(object(), payload)

    assert resolved == results
    assert header is None


def test_search_with_reranker_applies_header_and_ranks() -> None:
    settings = SimpleNamespace(
        reranker_enabled=True,
        reranker_model_path="/models/model.bin",
        reranker_model_sha256="abc123",
    )
    results = [
        _make_result("r1", 0.5),
        _make_result("r2", 0.4),
        _make_result("r3", 0.3),
    ]
    reranker = _StubReranker(["r2", "r1"])
    cache = _StubCache(reranker)

    service = RetrievalService(
        settings=settings,
        search_fn=lambda *_: list(results),
        reranker_cache=cache,
        reranker_top_k=2,
    )

    resolved, header = service.search(object(), HybridSearchRequest(query="query"))

    assert [item.id for item in resolved] == ["r2", "r1", "r3"]
    assert [item.rank for item in resolved] == [1, 2, 3]
    assert header == "model.bin"
    assert cache.calls == [(settings.reranker_model_path, settings.reranker_model_sha256)]
    assert reranker.calls and reranker.calls[0][0].id == "r1"


def test_search_swallows_reranker_failures() -> None:
    settings = SimpleNamespace(
        reranker_enabled=True,
        reranker_model_path="/models/model.bin",
        reranker_model_sha256=None,
    )
    results = [_make_result("r1", 0.5)]
    reranker = _StubReranker(["r1"], raise_error=True)
    cache = _StubCache(reranker)

    service = RetrievalService(
        settings=settings,
        search_fn=lambda *_: list(results),
        reranker_cache=cache,
        reranker_top_k=5,
    )

    resolved, header = service.search(object(), HybridSearchRequest(query="query"))

    assert [item.id for item in resolved] == ["r1"]
    assert header is None


def test_reset_reranker_cache_invokes_shared_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []

    def _reset() -> None:
        called.append(True)

    monkeypatch.setattr(retrieval_module._DEFAULT_RERANKER_CACHE, "reset", _reset)

    retrieval_module.reset_reranker_cache()

    assert called
