from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from theo.application.facades.database import get_engine
from theo.application.facades.settings import get_settings
from theo.services.api.app.db.models import Document
from theo.services.api.app.ingest.chunking import Chunk
from theo.services.api.app.ingest.exceptions import UnsupportedSourceError
from theo.services.api.app.ingest.persistence import persist_text_document
from theo.services.api.app.ingest.stages import IngestContext, Instrumentation


class DummyEmbeddingService:
    def embed(self, texts):
        return [[0.0] * max(1, len(text.split())) for text in texts]


def _make_chunk(text: str) -> Chunk:
    return Chunk(text=text, start_char=0, end_char=len(text), index=0)


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
