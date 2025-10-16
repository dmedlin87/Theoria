"""Tests for contradiction detection engine."""

from __future__ import annotations

import pytest

from theo.domain.discoveries.contradiction_engine import (
    ContradictionDiscoveryEngine,
)
from theo.domain.discoveries.models import DocumentEmbedding


def _has_transformers() -> bool:
    """Check if transformers library is available."""
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.fixture
def sample_documents():
    """Sample documents with contradictory claims."""
    return [
        DocumentEmbedding(
            document_id="doc1",
            title="Jesus is Fully Divine",
            abstract="This document argues that Jesus Christ is fully divine, equal to God the Father in essence and nature.",
            topics=["christology", "divinity", "theology"],
            verse_ids=[43001001],  # John 1:1
            embedding=[0.1] * 768,
            metadata={"author": "Author A"},
        ),
        DocumentEmbedding(
            document_id="doc2",
            title="Jesus is Subordinate to the Father",
            abstract="This document argues that Jesus is subordinate to God the Father, created by Him and not co-equal.",
            topics=["christology", "subordination", "theology"],
            verse_ids=[43014028],  # John 14:28
            embedding=[0.2] * 768,
            metadata={"author": "Author B"},
        ),
        DocumentEmbedding(
            document_id="doc3",
            title="The Gospel of Mark",
            abstract="A commentary on the Gospel of Mark, focusing on its narrative structure and theological themes.",
            topics=["gospel", "mark", "commentary"],
            verse_ids=[41001001],  # Mark 1:1
            embedding=[0.3] * 768,
            metadata={"author": "Author C"},
        ),
    ]


def test_contradiction_engine_initialization():
    """Test that engine initializes with correct defaults."""
    engine = ContradictionDiscoveryEngine()

    assert engine.model_name == "microsoft/deberta-v3-base-mnli"
    assert engine.contradiction_threshold == 0.7
    assert engine.min_confidence == 0.6
    assert engine._model is None  # Lazy loading


def test_contradiction_engine_custom_params():
    """Test engine with custom parameters."""
    engine = ContradictionDiscoveryEngine(
        model_name="custom-model",
        contradiction_threshold=0.8,
        min_confidence=0.5,
    )

    assert engine.model_name == "custom-model"
    assert engine.contradiction_threshold == 0.8
    assert engine.min_confidence == 0.5


def test_extract_claims(sample_documents):
    """Test claim extraction from documents."""
    engine = ContradictionDiscoveryEngine()
    claims = engine._extract_claims(sample_documents)

    assert len(claims) == 3
    assert claims[0]["document_id"] == "doc1"
    assert "divine" in claims[0]["text"].lower()
    assert claims[1]["document_id"] == "doc2"
    assert "subordinate" in claims[1]["text"].lower()


def test_extract_claims_empty_documents():
    """Test claim extraction with empty documents."""
    engine = ContradictionDiscoveryEngine()
    empty_docs = [
        DocumentEmbedding(
            document_id="empty",
            title="",
            abstract=None,
            topics=[],
            verse_ids=[],
            embedding=[0.1] * 768,
            metadata={},
        )
    ]

    claims = engine._extract_claims(empty_docs)
    assert len(claims) == 0


def test_extract_claims_truncates_long_text():
    """Test that long abstracts are truncated."""
    engine = ContradictionDiscoveryEngine()
    long_doc = DocumentEmbedding(
        document_id="long",
        title="Long Document",
        abstract="A" * 1000,  # Very long abstract
        topics=[],
        verse_ids=[],
        embedding=[0.1] * 768,
        metadata={},
    )

    claims = engine._extract_claims([long_doc])
    assert len(claims) == 1
    assert len(claims[0]["text"]) == 500  # Truncated


def test_infer_contradiction_type():
    """Test contradiction type inference."""
    engine = ContradictionDiscoveryEngine()

    # Theological
    assert engine._infer_contradiction_type({"christology", "other"}) == "theological"
    assert engine._infer_contradiction_type({"soteriology"}) == "theological"

    # Historical
    assert engine._infer_contradiction_type({"history", "other"}) == "historical"
    assert engine._infer_contradiction_type({"chronology"}) == "historical"

    # Textual
    assert engine._infer_contradiction_type({"textual", "other"}) == "textual"
    assert engine._infer_contradiction_type({"manuscript"}) == "textual"

    # Logical (default)
    assert engine._infer_contradiction_type({"random", "topics"}) == "logical"
    assert engine._infer_contradiction_type(set()) == "logical"


def test_detect_requires_minimum_documents():
    """Test that detect requires at least 2 documents."""
    engine = ContradictionDiscoveryEngine()

    # No documents
    result = engine.detect([])
    assert result == []

    # One document
    single_doc = [
        DocumentEmbedding(
            document_id="doc1",
            title="Single Document",
            abstract="Only one document",
            topics=[],
            verse_ids=[],
            embedding=[0.1] * 768,
            metadata={},
        )
    ]
    result = engine.detect(single_doc)
    assert result == []


@pytest.mark.slow
@pytest.mark.skipif(
    not _has_transformers(),
    reason="transformers library not installed",
)
def test_detect_contradictions(sample_documents):
    """Test full contradiction detection pipeline.
    
    Note: This test requires transformers and torch to be installed.
    It will download the NLI model on first run (~400MB).
    """
    engine = ContradictionDiscoveryEngine(
        contradiction_threshold=0.5,  # Lower threshold for testing
        min_confidence=0.4,
    )

    discoveries = engine.detect(sample_documents)

    # Should find at least one contradiction between doc1 and doc2
    assert len(discoveries) > 0

    # Check first discovery
    first = discoveries[0]
    assert first.confidence >= 0.4
    assert first.relevance_score > 0.0
    assert first.contradiction_type in ["theological", "historical", "textual", "logical"]
    assert first.document_a_id in ["doc1", "doc2"]
    assert first.document_b_id in ["doc1", "doc2"]
    assert first.document_a_id != first.document_b_id

    # Check metadata
    assert "nli_scores" in first.metadata
    assert "shared_topics" in first.metadata


@pytest.mark.slow
@pytest.mark.skipif(
    not _has_transformers(),
    reason="transformers library not installed",
)
def test_check_contradiction_direct():
    """Test NLI contradiction checking directly."""
    engine = ContradictionDiscoveryEngine()
    engine._load_model()

    # Clear contradiction
    result = engine._check_contradiction(
        "The sky is blue.",
        "The sky is red.",
    )

    assert isinstance(result["is_contradiction"], bool)
    assert isinstance(result["confidence"], float)
    assert 0.0 <= result["confidence"] <= 1.0
    assert "scores" in result
    assert "contradiction" in result["scores"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
