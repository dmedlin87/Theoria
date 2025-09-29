"""Tests for persistence helpers."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from theo.services.api.app.core.database import Base
from theo.services.api.app.ingest.chunking import Chunk
from theo.services.api.app.ingest.pipeline import persistence
from theo.services.api.app.ingest.pipeline.persistence import persist_text_document


class DummyEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.0 for _ in range(3)] for _ in texts]


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_persist_text_document_uses_injected_embedding(tmp_path, monkeypatch) -> None:
    session = _session()
    settings = SimpleNamespace(storage_root=tmp_path)
    monkeypatch.setattr(persistence, "refresh_creator_verse_rollups", lambda *args, **kwargs: None)

    embedding = DummyEmbeddingService()

    chunk = Chunk(text="Hello World", start_char=0, end_char=11, index=0)
    document = persist_text_document(
        session,
        chunks=[chunk],
        parser="plain",
        parser_version="1.0",
        frontmatter={},
        settings=settings,
        sha256="sha",
        source_type="txt",
        title="Test",
        source_url=None,
        text_content="Hello World",
        embedding_service=embedding,
    )

    assert embedding.calls == [["Hello World"]]
    storage_path = tmp_path / document.id
    assert storage_path.exists()
    normalized = storage_path / "normalized.json"
    assert normalized.exists()
