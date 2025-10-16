"""Tests for the connection discovery engine."""

from __future__ import annotations

import pytest

from theo.domain.discoveries.connection_engine import (
    ConnectionDiscoveryEngine,
)
from theo.domain.discoveries.models import DocumentEmbedding


def make_document(
    document_id: str,
    *,
    verses: list[int],
    title: str | None = None,
    topics: list[str] | None = None,
) -> DocumentEmbedding:
    return DocumentEmbedding(
        document_id=document_id,
        title=title or document_id,
        abstract=None,
        topics=topics or [],
        verse_ids=verses,
        embedding=[0.0],
        metadata={},
    )


def test_detects_connected_documents():
    """Documents sharing verses should be grouped into a connection discovery."""

    documents = [
        make_document("doc-a", verses=[10001001, 10001002], topics=["grace", "faith"]),
        make_document("doc-b", verses=[10001002, 10002003], topics=["faith", "history"]),
        make_document("doc-c", verses=[20001001], topics=["prophecy"]),
        make_document("doc-d", verses=[10001002, 30003003], topics=["grace"]),
    ]

    engine = ConnectionDiscoveryEngine()
    discoveries = engine.detect(documents)

    assert len(discoveries) == 1
    discovery = discoveries[0]
    assert set(discovery.metadata["relatedDocuments"]) == {"doc-a", "doc-b", "doc-d"}
    assert discovery.metadata["relatedVerses"] == [10001002]
    assert discovery.metadata["connectionData"]["sharedVerseCount"] == 1
    assert discovery.metadata["connectionData"]["edgeList"]
    for edge in discovery.metadata["connectionData"]["edgeList"]:
        assert edge["sharedVerseCount"] >= 1


def test_respects_minimum_shared_verses_threshold():
    """Edge weights below the threshold should be pruned from the graph."""

    documents = [
        make_document("doc-a", verses=[10001001, 10001002]),
        make_document("doc-b", verses=[10001002, 10002003]),  # only one shared verse
        make_document("doc-c", verses=[10001001, 10001002]),
    ]

    engine = ConnectionDiscoveryEngine(min_shared_verses=2)
    discoveries = engine.detect(documents)

    assert len(discoveries) == 1
    related = discoveries[0].metadata["relatedDocuments"]
    assert set(related) == {"doc-a", "doc-c"}
    # doc-b should be excluded because it shares only one verse with others
    assert "doc-b" not in related


def test_returns_empty_when_no_shared_verses():
    """Documents without overlapping verses should not produce discoveries."""

    documents = [
        make_document("doc-a", verses=[10001001]),
        make_document("doc-b", verses=[10002002]),
        make_document("doc-c", verses=[]),
    ]

    engine = ConnectionDiscoveryEngine()
    assert engine.detect(documents) == []


def test_constructor_validates_parameters():
    """Ensure guard rails exist for invalid configuration values."""

    with pytest.raises(ValueError):
        ConnectionDiscoveryEngine(min_shared_verses=0)

    with pytest.raises(ValueError):
        ConnectionDiscoveryEngine(min_documents=1)

    with pytest.raises(ValueError):
        ConnectionDiscoveryEngine(max_results=0)

