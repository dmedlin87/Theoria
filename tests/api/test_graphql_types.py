from __future__ import annotations

from datetime import datetime

from theo.domain import Document, DocumentId, DocumentMetadata
from theo.domain.research.overview import OverviewBullet
from theo.domain.research.scripture import Verse as DomainVerse
from theo.infrastructure.api.app.graphql import types as graphql_types


def test_document_metadata_type_from_domain() -> None:
    metadata = DocumentMetadata(
        title="Sample",
        source="tests",
        language="en",
        created_at=datetime(2024, 1, 2, 3, 4, 5),
        updated_at=datetime(2024, 6, 7, 8, 9, 10),
    )

    metadata_type = graphql_types.DocumentMetadataType.from_domain(metadata)

    assert metadata_type.title == "Sample"
    assert metadata_type.source == "tests"
    assert metadata_type.language == "en"
    assert metadata_type.created_at == datetime(2024, 1, 2, 3, 4, 5)
    assert metadata_type.updated_at == datetime(2024, 6, 7, 8, 9, 10)


def test_document_type_from_domain_converts_sequences() -> None:
    document = Document(
        id=DocumentId("doc-1"),
        metadata=DocumentMetadata(title="Doc", source="suite"),
        scripture_refs=("John.3.16", "John.3.17"),
        tags=("featured",),
        checksum="abc123",
    )

    document_type = graphql_types.DocumentType.from_domain(document)

    assert document_type.id == "doc-1"
    assert isinstance(document_type.metadata, graphql_types.DocumentMetadataType)
    assert document_type.scripture_refs == ["John.3.16", "John.3.17"]
    assert document_type.tags == ["featured"]
    assert document_type.checksum == "abc123"


def test_document_metadata_input_to_domain() -> None:
    metadata_input = graphql_types.DocumentMetadataInput(
        title="Doc", source="suite", language="el"
    )

    metadata = metadata_input.to_domain()

    assert metadata.title == "Doc"
    assert metadata.source == "suite"
    assert metadata.language == "el"


def test_document_input_to_domain_roundtrip() -> None:
    metadata_input = graphql_types.DocumentMetadataInput(title="Doc", source="suite")
    document_input = graphql_types.DocumentInput(
        id="doc-2",
        metadata=metadata_input,
        scripture_refs=["Gen.1.1"],
        tags=["alpha", "beta"],
        checksum="def456",
    )

    document = document_input.to_domain()

    assert document.id == DocumentId("doc-2")
    assert document.metadata == metadata_input.to_domain()
    assert document.scripture_refs == ("Gen.1.1",)
    assert document.tags == ("alpha", "beta")
    assert document.checksum == "def456"


def test_verse_type_from_domain() -> None:
    verse = DomainVerse(
        osis="John.3.16",
        translation="SBLGNT",
        text="For God so loved the world",
        book="John",
        chapter=3,
        verse=16,
    )

    verse_type = graphql_types.VerseType.from_domain(verse)

    assert verse_type.osis == "John.3.16"
    assert verse_type.translation == "SBLGNT"
    assert verse_type.text.startswith("For God")
    assert verse_type.book == "John"
    assert verse_type.chapter == 3
    assert verse_type.verse == 16


def test_insight_type_from_overview() -> None:
    bullet = OverviewBullet(summary="Concise", citations=("John 3:16", "John 3:17"))

    insight = graphql_types.InsightType.from_overview("consensus", bullet)

    assert insight.category == "consensus"
    assert insight.summary == "Concise"
    assert insight.citations == ["John 3:16", "John 3:17"]


def test_ingest_document_payload_from_document_id() -> None:
    payload = graphql_types.IngestDocumentPayload.from_document_id(DocumentId("doc-3"))

    assert payload.document_id == "doc-3"
