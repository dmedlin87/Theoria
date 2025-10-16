from __future__ import annotations

from theo.domain.discoveries.engine import (
    PatternDiscoveryEngine,
    _normalise_topics,
    _top_keywords,
)
from theo.domain.discoveries.models import DocumentEmbedding


def make_embedding(
    document_id: str,
    *,
    topics: list[str],
    verse_ids: list[int] | None = None,
    embedding: list[float] | None = None,
    keywords: object | None = None,
    title: str | None = None,
) -> DocumentEmbedding:
    metadata = {"keywords": keywords} if keywords is not None else None
    return DocumentEmbedding(
        document_id=document_id,
        title=title or document_id.title(),
        abstract=None,
        topics=topics,
        verse_ids=verse_ids if verse_ids is not None else [],
        embedding=embedding if embedding is not None else [1.0, 0.0, 0.0],
        metadata=metadata,
    )


def test_normalise_topics_filters_empty_and_duplicates() -> None:
    topics = ["Faith", "  Hope  ", "", "Faith", "LOVE", "love", "   "]

    result = _normalise_topics(topics)

    assert result == ["faith", "hope", "love"]


def test_top_keywords_includes_topics_and_metadata() -> None:
    documents = [
        make_embedding(
            "doc-1",
            topics=["Faith", "  Hope  ", ""],
            keywords="Grace",
        ),
        make_embedding(
            "doc-2",
            topics=["FAITH", "Love"],
            keywords={"primary": "Love", "secondary": "Charity"},
        ),
        make_embedding(
            "doc-3",
            topics=["Hope"],
            keywords=["Perseverance", "Faith"],
        ),
    ]

    keywords = _top_keywords(documents, limit=5)

    assert keywords == ["faith", "hope", "love", "grace", "charity"]


def test_pattern_discovery_engine_detects_cluster_and_builds_snapshot() -> None:
    documents = [
        make_embedding(
            "doc-1",
            topics=["Faith", "Hope"],
            verse_ids=[10001001, 10001002],
            embedding=[1.0, 0.0, 0.0],
            keywords=["Grace", "Faith"],
            title="First Document",
        ),
        make_embedding(
            "doc-2",
            topics=["FAITH", "Love"],
            verse_ids=[10001002, 10001003],
            embedding=[0.99, 0.01, 0.0],
            keywords={"primary": "Love", "secondary": "Charity"},
            title="Second Document",
        ),
        make_embedding(
            "doc-3",
            topics=["Hope", "Love"],
            verse_ids=[10001003, 10001004],
            embedding=[0.98, 0.02, 0.0],
            keywords=["Perseverance"],
            title="Third Document",
        ),
        make_embedding(
            "doc-4",
            topics=["Noise"],
            verse_ids=[10001005],
            embedding=[float("nan"), 0.0, 0.0],
            keywords=None,
            title="Noisy Document",
        ),
        make_embedding(
            "doc-5",
            topics=["Ignored"],
            verse_ids=[10001006],
            embedding=[],
            keywords=None,
            title="Ignored Document",
        ),
    ]

    engine = PatternDiscoveryEngine(eps=0.35, min_cluster_size=2)

    discoveries, snapshot = engine.detect(documents)

    assert len(discoveries) == 1

    discovery = discoveries[0]
    assert discovery.title.startswith("Pattern detected")
    assert "Faith" in discovery.title
    assert discovery.confidence == 0.95
    assert discovery.relevance_score == 0.95
    assert "cluster of 3 documents" in discovery.description

    related_docs = discovery.metadata["relatedDocuments"]
    assert related_docs == ["doc-1", "doc-2", "doc-3"]

    related_topics = discovery.metadata["relatedTopics"]
    assert related_topics == ["faith", "love", "hope", "grace", "charity"]

    pattern_data = discovery.metadata["patternData"]
    assert pattern_data["clusterSize"] == 3
    assert pattern_data["sharedThemes"] == related_topics
    assert pattern_data["keyVerses"] == [10001001, 10001002, 10001003, 10001004]

    assert discovery.metadata["titles"] == [
        "First Document",
        "Second Document",
        "Third Document",
    ]

    assert snapshot.document_count == 3
    assert snapshot.metadata["pattern_cluster_count"] == 1
    assert snapshot.verse_coverage == {
        "unique_count": 4,
        "sample": [10001001, 10001002, 10001003, 10001004],
    }
    assert snapshot.dominant_themes["top_topics"][:3] == ["faith", "hope", "love"]


def test_pattern_discovery_engine_returns_empty_when_insufficient_documents() -> None:
    documents = [
        make_embedding(
            "doc-a",
            topics=["Faith"],
            verse_ids=[10001001],
            embedding=[1.0, 0.0, 0.0],
        ),
        make_embedding(
            "doc-b",
            topics=["Hope"],
            verse_ids=[10001002],
            embedding=[0.99, 0.01, 0.0],
        ),
    ]

    engine = PatternDiscoveryEngine(eps=0.35, min_cluster_size=3)

    discoveries, snapshot = engine.detect(documents)

    assert discoveries == []
    assert snapshot.document_count == 2
    assert snapshot.metadata["pattern_cluster_count"] == 0
    assert snapshot.verse_coverage["unique_count"] == 2
    assert snapshot.dominant_themes["top_topics"] == ["faith", "hope"]
