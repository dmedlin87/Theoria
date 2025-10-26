"""Tests for :mod:`theo.domain.documents` value objects."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from theo.domain.documents import Document, DocumentId, DocumentMetadata


def test_document_metadata_initialisation_and_defaults() -> None:
    created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    metadata = DocumentMetadata(
        title="Theologia",
        source="Research",
        language="en",
        created_at=created_at,
    )

    assert metadata.title == "Theologia"
    assert metadata.source == "Research"
    assert metadata.language == "en"
    assert metadata.created_at is created_at
    assert metadata.updated_at is None


def test_document_aggregate_stores_immutable_state() -> None:
    doc_id = DocumentId("doc-1")
    metadata = DocumentMetadata(title="Doc", source="UnitTest")

    document = Document(
        id=doc_id,
        metadata=metadata,
        scripture_refs=("Gen.1.1", "John.3.16"),
        tags=("theology", "study"),
        checksum="abc123",
    )

    assert document.id == doc_id
    assert document.metadata is metadata
    assert document.scripture_refs == ("Gen.1.1", "John.3.16")
    assert document.tags == ("theology", "study")
    assert document.checksum == "abc123"
    assert document == Document(
        id=doc_id,
        metadata=metadata,
        scripture_refs=("Gen.1.1", "John.3.16"),
        tags=("theology", "study"),
        checksum="abc123",
    )

    with pytest.raises(FrozenInstanceError):
        document.tags += ("extra",)  # type: ignore[assignment]


def test_document_defaults_are_empty_tuples() -> None:
    doc = Document(
        id=DocumentId("empty"),
        metadata=DocumentMetadata(title="Empty", source="Unknown"),
        scripture_refs=(),
    )

    assert doc.tags == ()
    assert doc.checksum is None
