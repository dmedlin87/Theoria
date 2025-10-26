"""Tests for discovery domain models."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from theo.domain.discoveries.models import (
    CorpusSnapshotSummary,
    DiscoveryType,
    DocumentEmbedding,
    PatternDiscovery,
)


def test_document_embedding_behaves_like_value_object() -> None:
    embedding = DocumentEmbedding(
        document_id="doc-1",
        title="Theology and Science",
        abstract="A study",
        topics=("creation", "science"),
        verse_ids=(1, 2, 3),
        embedding=(0.1, 0.2, 0.3),
        metadata={"source": "corpus"},
    )
    duplicate = DocumentEmbedding(
        document_id="doc-1",
        title="Theology and Science",
        abstract="A study",
        topics=("creation", "science"),
        verse_ids=(1, 2, 3),
        embedding=(0.1, 0.2, 0.3),
        metadata={"source": "corpus"},
    )

    assert embedding == duplicate
    with pytest.raises(FrozenInstanceError):
        embedding.title = "Changed"  # type: ignore[misc]


def test_pattern_discovery_metadata_is_isolated() -> None:
    first = PatternDiscovery(
        title="Pattern A",
        description="Description",
        confidence=0.8,
        relevance_score=0.9,
    )
    second = PatternDiscovery(
        title="Pattern B",
        description="Description",
        confidence=0.7,
        relevance_score=0.85,
    )

    first.metadata["key"] = "value"

    assert first.metadata == {"key": "value"}
    assert second.metadata == {}


def test_corpus_snapshot_summary_defaults() -> None:
    summary = CorpusSnapshotSummary()

    assert summary.document_count == 0
    assert summary.verse_coverage == {}
    assert summary.snapshot_date.tzinfo is UTC
    assert abs(summary.snapshot_date.timestamp() - datetime.now(UTC).timestamp()) < 1


def test_discovery_type_enum_members() -> None:
    assert DiscoveryType.PATTERN.value == "pattern"
    assert DiscoveryType.CONTRADICTION.value == "contradiction"
