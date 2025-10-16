from __future__ import annotations

import math

import pytest

from theo.domain.discoveries.anomaly_engine import (
    AnomalyDiscovery,
    AnomalyDiscoveryEngine,
)
from theo.domain.discoveries.models import DocumentEmbedding


def _document(
    document_id: str,
    embedding: list[float],
    *,
    title: str | None = None,
    topics: list[str] | None = None,
) -> DocumentEmbedding:
    return DocumentEmbedding(
        document_id=document_id,
        title=title or document_id,
        abstract=None,
        topics=topics or [],
        verse_ids=[],
        embedding=embedding,
        metadata={"keywords": topics or []},
    )


def test_anomaly_engine_flags_outlier():
    engine = AnomalyDiscoveryEngine(
        contamination=0.2,
        min_documents=5,
        random_state=42,
        max_anomalies=3,
    )

    documents = [
        _document("doc-normal-1", [0.0, 0.1, 0.0], topics=["theology"]),
        _document("doc-normal-2", [0.1, 0.0, 0.05], topics=["history"]),
        _document("doc-normal-3", [0.05, 0.05, 0.1], topics=["history"]),
        _document("doc-normal-4", [0.02, 0.02, 0.02], topics=["ethics"]),
        _document("doc-normal-5", [0.03, 0.01, 0.04], topics=["ethics"]),
        _document("doc-outlier", [4.0, 4.0, 4.0], topics=["apocrypha"]),
    ]

    anomalies = engine.detect(documents)

    assert anomalies, "Expected at least one anomaly to be detected"
    top = anomalies[0]
    assert isinstance(top, AnomalyDiscovery)
    assert top.document_id == "doc-outlier"
    assert top.anomaly_score > 0
    assert top.confidence >= 0.5
    assert "relatedDocuments" in top.metadata
    assert top.metadata["anomalyData"]["score"] == top.anomaly_score


def test_anomaly_engine_is_deterministic_with_seed():
    documents = [
        _document("doc1", [0.0, 0.0, 0.0]),
        _document("doc2", [0.1, 0.1, 0.1]),
        _document("doc3", [0.2, 0.2, 0.2]),
        _document("doc4", [0.3, 0.3, 0.3]),
        _document("doc-outlier", [5.0, 5.0, 5.0]),
    ]

    engine = AnomalyDiscoveryEngine(random_state=99, contamination=0.2, min_documents=5)
    first_run = engine.detect(documents)
    second_run = engine.detect(documents)

    assert first_run == second_run


@pytest.mark.parametrize(
    "documents",
    [
        [],
        [_document("doc1", [0.0, 0.0, 0.0])],
        [
            _document("doc1", [0.0, 0.0, math.nan]),
            _document("doc2", [0.0, 0.0, 0.0]),
            _document("doc3", [0.0, 0.0, 0.0]),
            _document("doc4", [0.0, 0.0, 0.0]),
        ],
    ],
)
def test_anomaly_engine_edge_cases(documents):
    engine = AnomalyDiscoveryEngine(min_documents=3)
    assert engine.detect(documents) == []
