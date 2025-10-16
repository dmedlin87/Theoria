"""Tests for the connection discovery engine."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from theo.domain.discoveries.connection_engine import (
    ConnectionDiscoveryEngine,
)
from theo.domain.discoveries.models import DocumentEmbedding


def make_document(
    document_id: str,
    *,
    verses: Sequence[object],
    title: str | None = None,
    topics: Sequence[str] | None = None,
) -> DocumentEmbedding:
    return DocumentEmbedding(
        document_id=document_id,
        title=title or document_id,
        abstract=None,
        topics=list(topics or []),
        verse_ids=list(verses),
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


def test_detects_shared_topics_and_generates_descriptive_output():
    """Whitespace and case in topics should be normalised for scoring."""

    documents = [
        make_document(
            "doc-1",
            verses=[101, "psalm-101", 202],
            title="  First  ",
            topics=["Grace", "Community"],
        ),
        make_document(
            "doc-2",
            verses=[202, 303],
            title=" ",
            topics=[" grace ", "History"],
        ),
        make_document(
            "doc-3",
            verses=["no-shared"],
            title="Ignored",
            topics=["Grace"],
        ),
    ]

    engine = ConnectionDiscoveryEngine(min_shared_verses=1, max_results=5)
    discoveries = engine.detect(documents)

    assert len(discoveries) == 1
    discovery = discoveries[0]
    assert discovery.title == "Connection between First and doc-2"
    assert "Detected a network of 2 documents" in discovery.description
    assert "Key shared verses include 202" in discovery.description
    assert "Common themes: Grace" in discovery.description
    assert discovery.metadata["relatedVerses"] == [202]
    assert discovery.metadata["relatedTopics"] == ["grace"]
    assert discovery.metadata["relatedDocuments"] == ["doc-1", "doc-2"]
    assert discovery.metadata["connectionData"]["sharedVerseCount"] == 1
    assert discovery.metadata["connectionData"]["graphDensity"] == pytest.approx(1.0)
    assert discovery.confidence == pytest.approx(0.8)
    assert discovery.relevance_score == pytest.approx(0.55)


def test_detect_limits_results_to_max_results():
    """Only the top-ranked discoveries should be returned."""

    documents = [
        make_document(
            "doc-a",
            verses=[1, 2],
            topics=["unity", "hope"],
        ),
        make_document(
            "doc-b",
            verses=[1, 2],
            topics=["unity", "service"],
        ),
        make_document(
            "doc-c",
            verses=[10, 11, 12],
            topics=["wisdom", "love"],
        ),
        make_document(
            "doc-d",
            verses=[10, 11, 12],
            topics=["wisdom", "Justice"],
        ),
        make_document(
            "doc-e",
            verses=[10, 11, 12],
            topics=["wisdom", "mercy"],
        ),
    ]

    engine = ConnectionDiscoveryEngine(max_results=1)
    discoveries = engine.detect(documents)

    assert len(discoveries) == 1
    related_docs = discoveries[0].metadata["relatedDocuments"]
    assert set(related_docs) == {"doc-c", "doc-d", "doc-e"}
    assert discoveries[0].confidence == pytest.approx(0.95)

