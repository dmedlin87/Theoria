from __future__ import annotations

import hashlib
from pathlib import Path

import joblib  # type: ignore[import]
import pytest
from fastapi.testclient import TestClient

from theo.services.api.app.core.settings import get_settings
from theo.services.api.app.main import app
from theo.services.api.app.models.search import HybridSearchResult
from theo.services.api.app.routes import search as search_route


class _WeightedModel:
    def __init__(self, feature_index: int):
        self._index = feature_index

    def predict(self, features: list[list[float]]) -> list[float]:
        return [row[self._index] for row in features]


def _build_result(
    suffix: int,
    *,
    score: float,
    lexical: float = 0.0,
    vector: float = 0.0,
    document_score: float | None = None,
    document_rank: int | None = None,
    osis_distance: float | None = None,
) -> HybridSearchResult:
    return HybridSearchResult(
        id=f"p{suffix}",
        document_id=f"d{suffix}",
        text=f"Passage {suffix}",
        raw_text=f"Raw {suffix}",
        osis_ref=None,
        start_char=None,
        end_char=None,
        page_no=None,
        t_start=None,
        t_end=None,
        score=score,
        meta={},
        document_title=f"Document {suffix}",
        snippet=f"Snippet {suffix}",
        rank=suffix,
        lexical_score=lexical,
        vector_score=vector,
        document_score=document_score,
        document_rank=document_rank,
        osis_distance=osis_distance,
    )


def _stub_results() -> list[HybridSearchResult]:
    return [
        _build_result(1, score=0.3, lexical=0.1, vector=0.4, document_rank=1),
        _build_result(2, score=0.4, lexical=0.9, vector=0.2, document_rank=2),
        _build_result(3, score=0.2, lexical=0.2, vector=0.1, document_rank=3),
    ]


@pytest.fixture(autouse=True)
def _reset_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_ROOT", raising=False)
    monkeypatch.delenv("RERANKER_ENABLED", raising=False)
    monkeypatch.delenv("RERANKER_MODEL_PATH", raising=False)
    monkeypatch.delenv("RERANKER_MODEL_SHA256", raising=False)
    get_settings.cache_clear()
    search_route.reset_reranker_cache()


def test_search_rejects_reranker_with_hash_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    storage_root = tmp_path / "storage"
    reranker_root = storage_root / "rerankers"
    reranker_root.mkdir(parents=True)
    model_path = reranker_root / "stub.joblib"

    joblib.dump(_WeightedModel(feature_index=2), model_path)
    original_bytes = model_path.read_bytes()
    digest = hashlib.sha256(original_bytes).hexdigest()
    model_path.write_bytes(original_bytes + b"tampered")

    results = _stub_results()

    def _fake_search(session, request):  # type: ignore[unused-argument]
        return [item.model_copy(deep=True) for item in results]

    monkeypatch.setattr(search_route, "hybrid_search", _fake_search)
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("RERANKER_ENABLED", "true")
    monkeypatch.setenv("RERANKER_MODEL_PATH", str(model_path))
    monkeypatch.setenv("RERANKER_MODEL_SHA256", digest)
    get_settings.cache_clear()
    search_route.reset_reranker_cache()

    with caplog.at_level("ERROR"):
        with TestClient(app) as client:
            response = client.get("/search", params={"q": "query"})

    payload = response.json()
    assert [entry["id"] for entry in payload["results"]] == [result.id for result in results]
    assert "X-Reranker" not in response.headers

    failures = [record for record in caplog.records if record.message == "search.reranker_load_failed"]
    assert failures, "Expected reranker load failure to be logged"
    failure = failures[-1]
    assert getattr(failure, "model_path", "") == str(model_path)
    assert "Hash mismatch" in getattr(failure, "error", "")
