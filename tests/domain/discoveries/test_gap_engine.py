"""Unit tests for the theological gap discovery engine."""

from __future__ import annotations

import pytest

from theo.domain.discoveries.gap_engine import GapDiscoveryEngine
from theo.domain.discoveries.models import DocumentEmbedding


class FakeTopicModel:
    """Simple BERTopic stand-in for deterministic testing."""

    def fit_transform(self, documents: list[str]):  # pragma: no cover - simple helper
        self.documents = documents
        assignments: list[int] = []
        for text in documents:
            lowered = text.lower()
            if "grace" in lowered or "faith" in lowered:
                assignments.append(0)
            elif "kingdom" in lowered or "eschatology" in lowered:
                assignments.append(1)
            else:
                assignments.append(-1)
        return assignments, None

    def get_topic(self, topic_id: int):  # pragma: no cover - simple helper
        topics = {
            0: [("grace", 0.6), ("faith", 0.5), ("salvation", 0.4)],
            1: [("kingdom", 0.6), ("eschatology", 0.5), ("hope", 0.4)],
        }
        return topics.get(topic_id, [])


@pytest.fixture
def reference_topics():
    return [
        {
            "name": "Justification by Faith",
            "summary": "Classic Protestant articulation of salvation by grace through faith in Christ alone.",
            "keywords": [
                "justification",
                "faith",
                "grace",
                "righteousness",
                "salvation",
                "atonement",
            ],
            "scriptures": ["Romans 3:21-26"],
        },
        {
            "name": "Trinity and the Godhead",
            "summary": "Doctrinal core describing the triune life of God.",
            "keywords": ["trinity", "godhead", "persons"],
            "scriptures": ["Matthew 28:19"],
        },
    ]


@pytest.fixture
def sample_documents():
    return [
        DocumentEmbedding(
            document_id="doc1",
            title="Grace that saves",
            abstract="Explores how divine grace justifies believers through faith alone.",
            topics=["soteriology", "grace"],
            verse_ids=[45003024],
            embedding=[0.1, 0.2, 0.3],
            metadata={"author": "Author A"},
        ),
        DocumentEmbedding(
            document_id="doc2",
            title="Kingdom Hope",
            abstract="Examines eschatological themes about the coming kingdom of God.",
            topics=["eschatology", "kingdom"],
            verse_ids=[66021001],
            embedding=[0.2, 0.1, 0.4],
            metadata={"author": "Author B"},
        ),
    ]


def test_gap_engine_initialization_defaults():
    engine = GapDiscoveryEngine(topic_model=FakeTopicModel(), reference_topics=[])

    assert engine.min_similarity == pytest.approx(0.35)
    assert engine.max_results == 10
    assert engine._topic_model is not None


def test_gap_engine_detect_identifies_missing_topics(sample_documents, reference_topics):
    engine = GapDiscoveryEngine(
        min_similarity=0.4,
        topic_model=FakeTopicModel(),
        reference_topics=reference_topics,
    )

    discoveries = engine.detect(sample_documents)

    assert len(discoveries) == 1
    gap = discoveries[0]
    assert gap.reference_topic == "Trinity and the Godhead"
    assert "limited engagement" in gap.description
    assert "trinity" in gap.missing_keywords
    assert gap.related_documents == []
    assert 0.5 <= gap.confidence <= 0.95
    assert 0.45 <= gap.relevance_score <= 0.9
    assert "gapData" in gap.metadata
    assert gap.metadata["gapData"]["referenceTopic"] == "Trinity and the Godhead"
    assert gap.metadata["gapData"]["coverageRatio"] == pytest.approx(0.0)
    assert gap.metadata["gapData"]["gapIntensity"] == pytest.approx(1.0)


def test_gap_engine_detect_handles_empty_documents(reference_topics):
    engine = GapDiscoveryEngine(topic_model=FakeTopicModel(), reference_topics=reference_topics)
    empty_doc = DocumentEmbedding(
        document_id="doc-empty",
        title="",
        abstract=None,
        topics=[],
        verse_ids=[],
        embedding=[0.0, 0.0, 0.0],
        metadata={},
    )

    discoveries = engine.detect([empty_doc])

    assert discoveries == []


def test_gap_engine_detect_with_no_reference_topics(sample_documents):
    engine = GapDiscoveryEngine(topic_model=FakeTopicModel(), reference_topics=[])

    assert engine.detect(sample_documents) == []


def test_gap_engine_coerce_keywords_handles_varied_inputs():
    engine = GapDiscoveryEngine(topic_model=FakeTopicModel(), reference_topics=[])

    assert engine._coerce_keywords("  Grace  ") == ["grace"]

    sequence_result = engine._coerce_keywords([
        " Grace ",
        "faith",
        "Faith",
        123,
        None,
        "hope",
    ])
    assert sequence_result == ["grace", "faith", "hope"]

    mapping_result = engine._coerce_keywords(
        {"Trinity": "Persons", "Godhead": 1, " persons ": "Communion"}
    )
    assert mapping_result == ["trinity", "godhead", "persons", "communion"]


def test_gap_engine_prepare_document_text_prefers_title_and_abstract():
    document = DocumentEmbedding(
        document_id="doc-title",
        title="  Grace and Faith ",
        abstract=" Exploring doctrine ",
        topics=["grace", "faith"],
        verse_ids=[],
        embedding=[],
        metadata=None,
    )

    prepared = GapDiscoveryEngine._prepare_document_text(document)

    assert prepared == "Grace and Faith Exploring doctrine"


def test_gap_engine_prepare_document_text_falls_back_to_topics():
    document = DocumentEmbedding(
        document_id="doc-topics",
        title="  ",
        abstract=None,
        topics=["Grace", "Faith", ""],
        verse_ids=[],
        embedding=[],
        metadata=None,
    )

    prepared = GapDiscoveryEngine._prepare_document_text(document)

    assert prepared == "Grace Faith"


def test_gap_engine_normalise_reference_topic_handles_alternate_fields():
    engine = GapDiscoveryEngine(topic_model=FakeTopicModel(), reference_topics=[])

    result = engine._normalise_reference_topic(
        {
            "name": "  Trinity  ",
            "summary": "  God is three persons ",
            "tags": ["Trinity", "Godhead", ""],
            "references": [" Matthew 28:19 ", None, 123],
        }
    )

    assert result == {
        "name": "Trinity",
        "summary": "God is three persons",
        "keywords": ["trinity", "godhead"],
        "scriptures": ["Matthew 28:19"],
    }


def test_gap_engine_confidence_reflects_similarity_gap(sample_documents, reference_topics):
    engine = GapDiscoveryEngine(
        min_similarity=0.6,
        topic_model=FakeTopicModel(),
        reference_topics=reference_topics,
    )

    discoveries = engine.detect(sample_documents)

    justification_gap = next(
        item for item in discoveries if item.reference_topic == "Justification by Faith"
    )

    assert justification_gap.confidence < 0.9
    assert justification_gap.metadata["gapData"]["coverageRatio"] == pytest.approx(0.5)
    assert justification_gap.metadata["gapData"]["similarityScore"] == pytest.approx(0.5)


def test_gap_engine_respects_max_results(sample_documents):
    reference_topics = [
        {
            "name": "Topic A",
            "summary": "",
            "keywords": ["alpha", "beta"],
            "scriptures": [],
        },
        {
            "name": "Topic B",
            "summary": "",
            "keywords": ["gamma"],
            "scriptures": [],
        },
        {
            "name": "Topic C",
            "summary": "",
            "keywords": ["delta"],
            "scriptures": [],
        },
    ]

    engine = GapDiscoveryEngine(
        min_similarity=0.4,
        max_results=2,
        topic_model=FakeTopicModel(),
        reference_topics=reference_topics,
    )

    discoveries = engine.detect(sample_documents)

    assert len(discoveries) == 2
    assert all(d.metadata["gapData"]["gapIntensity"] == pytest.approx(1.0) for d in discoveries)
