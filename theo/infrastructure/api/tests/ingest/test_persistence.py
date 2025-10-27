from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from theo.application.graph import GraphDocumentProjection
from theo.application.facades.database import get_engine
from theo.application.facades.settings import get_settings
from theo.adapters.persistence.models import Document
from theo.infrastructure.api.app.ingest.chunking import Chunk
from theo.infrastructure.api.app.ingest.exceptions import UnsupportedSourceError
from theo.infrastructure.api.app.ingest.persistence import persist_text_document
from theo.infrastructure.api.app.ingest.stages import IngestContext, Instrumentation


class DummyEmbeddingService:
    def embed(self, texts):
        return [[0.0] * max(1, len(text.split())) for text in texts]


def _make_chunk(text: str) -> Chunk:
    return Chunk(text=text, start_char=0, end_char=len(text), index=0)


class RecordingProjector:
    def __init__(self) -> None:
        self.calls: list[GraphDocumentProjection] = []

    def project_document(self, projection: GraphDocumentProjection) -> None:
        self.calls.append(projection)

    def remove_document(self, document_id: str) -> None:  # pragma: no cover - unused hook
        return None


def test_persist_text_document_creates_storage():
    engine = get_engine()
    settings = get_settings()
    context = IngestContext(
        settings=settings,
        embedding_service=DummyEmbeddingService(),
        instrumentation=Instrumentation(span=None),
    )
    chunk = _make_chunk("In the beginning was the Word")

    with Session(engine) as session:
        document = persist_text_document(
            session,
            context=context,
            chunks=[chunk],
            parser="plain",
            parser_version="0.0",
            frontmatter={"title": "Test Doc"},
            sha256="sha-test-123",
            source_type="txt",
            title="Test Doc",
            source_url=None,
            text_content=chunk.text,
        )

        storage_path = Path(document.storage_path)
        assert storage_path.exists()
        assert (storage_path / "frontmatter.json").exists()

        stored = session.query(Document).filter(Document.id == document.id).one()
        assert stored.title == "Test Doc"


def test_persist_text_document_enforces_unique_sha():
    engine = get_engine()
    settings = get_settings()
    context = IngestContext(
        settings=settings,
        embedding_service=DummyEmbeddingService(),
        instrumentation=Instrumentation(span=None),
    )
    chunk = _make_chunk("In the beginning was the Word")

    with Session(engine) as session:
        persist_text_document(
            session,
            context=context,
            chunks=[chunk],
            parser="plain",
            parser_version="0.0",
            frontmatter={"title": "Test Doc"},
            sha256="sha-test-duplicate",
            source_type="txt",
            title="Test Doc",
            source_url=None,
            text_content=chunk.text,
        )

        with pytest.raises(UnsupportedSourceError):
            persist_text_document(
                session,
                context=context,
                chunks=[chunk],
                parser="plain",
                parser_version="0.0",
                frontmatter={"title": "Test Doc"},
                sha256="sha-test-duplicate",
                source_type="txt",
                title="Duplicate Doc",
                source_url=None,
                text_content=chunk.text,
            )


def test_persist_text_document_projects_graph():
    engine = get_engine()
    settings = get_settings()
    projector = RecordingProjector()
    context = IngestContext(
        settings=settings,
        embedding_service=DummyEmbeddingService(),
        instrumentation=Instrumentation(span=None),
        graph_projector=projector,
    )
    chunk = _make_chunk("Grace abounds")
    frontmatter = {
        "title": "Graph Doc",
        "topics": ["Grace"],
        "osis_refs": ["John.3.16"],
    }

    with Session(engine) as session:
        document = persist_text_document(
            session,
            context=context,
            chunks=[chunk],
            parser="plain",
            parser_version="0.0",
            frontmatter=frontmatter,
            sha256="sha-graph-1",
            source_type="txt",
            title="Graph Doc",
            source_url=None,
            text_content=chunk.text,
        )
        document_id = document.id

    assert projector.calls, "Expected graph projection to be invoked"
    projection = projector.calls[-1]
    assert projection.document_id == document_id
    assert projection.verses == ("John.3.16",)
    assert projection.concepts == ("Grace",)
