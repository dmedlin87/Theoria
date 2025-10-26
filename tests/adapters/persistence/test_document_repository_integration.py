from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import importlib
import importlib.util
import sys
import types

try:
    importlib.import_module("theo.domain.discoveries")
except ModuleNotFoundError:
    mock_module = types.ModuleType("theo.domain.discoveries")
    mock_module.__path__ = []  # mark as package for submodule imports
    mock_module.__spec__ = importlib.util.spec_from_loader(
        "theo.domain.discoveries", loader=None, is_package=True
    )

    @dataclass
    class DocumentEmbedding:
        document_id: str
        title: str
        abstract: str | None = None
        topics: list[str] | None = None
        verse_ids: list[int] | None = None
        embedding: list[float] | None = None
        metadata: dict[str, object] | None = None

    mock_module.DocumentEmbedding = DocumentEmbedding
    sys.modules["theo.domain.discoveries"] = mock_module

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from theo.adapters.persistence import Base
from theo.adapters.persistence.document_repository import SQLAlchemyDocumentRepository
from theo.adapters.persistence.models import Document, Passage


@pytest.fixture()
def in_memory_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _add_document(
    session: Session,
    *,
    document_id: str,
    collection: str,
    title: str | None = None,
    topics: list[str] | None = None,
    created_at: datetime | None = None,
    passages: list[Passage] | None = None,
) -> Document:
    document = Document(
        id=document_id,
        title=title,
        collection=collection,
        topics=topics,
        abstract="Created document",
    )
    if created_at is not None:
        document.created_at = created_at
        document.updated_at = created_at
    if passages:
        document.passages.extend(passages)
    session.add(document)
    session.commit()
    return document


@contextmanager
def _record_selects(session: Session):
    statements: list[str] = []
    engine = session.get_bind()

    def _before_execute(
        conn, cursor, statement, parameters, context, executemany
    ):  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _before_execute)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _before_execute)


def test_list_with_embeddings_returns_averaged_vectors(in_memory_session: Session) -> None:
    repo = SQLAlchemyDocumentRepository(in_memory_session)

    passage_one = Passage(
        text="In the beginning",
        raw_text="In the beginning",
        osis_ref="Gen.1.1",
        osis_verse_ids=[1001001, 1001002],
        embedding=[1.0, 2.0, 3.0],
    )
    passage_two = Passage(
        text="God created the heavens",
        raw_text="God created the heavens",
        osis_ref="Gen.1.2",
        osis_verse_ids=[1001002, 1001003],
        embedding=[2.0, 4.0, 6.0],
    )
    _add_document(
        in_memory_session,
        document_id="doc-1",
        collection="user-1",
        title="Creation",
        topics=["creation"],
        passages=[passage_one, passage_two],
    )
    # Document without embeddings should be ignored gracefully
    empty_passage = Passage(text="No embedding", raw_text="No embedding", osis_ref=None)
    _add_document(
        in_memory_session,
        document_id="doc-2",
        collection="user-1",
        title="Empty",
        passages=[empty_passage],
    )

    embeddings = repo.list_with_embeddings("user-1")

    assert len(embeddings) == 1
    embedding = embeddings[0]
    assert embedding.document_id == "doc-1"
    assert embedding.title == "Creation"
    assert embedding.topics == ["creation"]
    assert embedding.verse_ids == [1001001, 1001002, 1001003]
    assert embedding.embedding == pytest.approx([1.5, 3.0, 4.5])


def test_document_repository_filters_by_created_timestamp(in_memory_session: Session) -> None:
    repo = SQLAlchemyDocumentRepository(in_memory_session)
    now = datetime.now(timezone.utc)
    _add_document(
        in_memory_session,
        document_id="recent",
        collection="alpha",
        title="Recent Document",
        created_at=now - timedelta(hours=1),
    )
    _add_document(
        in_memory_session,
        document_id="old",
        collection="alpha",
        title="Old Document",
        created_at=now - timedelta(days=2),
    )

    results = repo.list_created_since(now - timedelta(days=1))

    assert [doc.id for doc in results] == ["recent"]
    assert results[0].title == "Recent Document"


def test_document_repository_get_by_id_returns_dto(in_memory_session: Session) -> None:
    repo = SQLAlchemyDocumentRepository(in_memory_session)
    stored = _add_document(
        in_memory_session,
        document_id="doc-lookup",
        collection="beta",
        title="Lookup Document",
    )

    dto = repo.get_by_id(stored.id)

    assert dto is not None
    assert dto.id == stored.id
    assert dto.title == "Lookup Document"
    assert dto.collection == "beta"


def test_get_by_id_eager_loads_passages(in_memory_session: Session) -> None:
    repo = SQLAlchemyDocumentRepository(in_memory_session)
    passage = Passage(text="Loaded", raw_text="Loaded", osis_ref="Gen.1.1")
    stored = _add_document(
        in_memory_session,
        document_id="doc-eager",
        collection="gamma",
        passages=[passage],
    )

    with _record_selects(in_memory_session) as statements:
        dto = repo.get_by_id(stored.id)
        assert dto is not None
        assert len(dto.passages) == 1

    select_statements = [stmt for stmt in statements if stmt.lstrip().upper().startswith("SELECT")]
    assert len(select_statements) <= 2


def test_list_created_since_uses_selectinload(in_memory_session: Session) -> None:
    repo = SQLAlchemyDocumentRepository(in_memory_session)
    now = datetime.now(timezone.utc)
    passages = [
        Passage(text="First", raw_text="First", osis_ref="Gen.1.1"),
        Passage(text="Second", raw_text="Second", osis_ref="Gen.1.2"),
    ]
    _add_document(
        in_memory_session,
        document_id="doc-recent",
        collection="delta",
        created_at=now - timedelta(hours=1),
        passages=passages,
    )
    _add_document(
        in_memory_session,
        document_id="doc-older",
        collection="delta",
        created_at=now - timedelta(days=2),
    )

    with _record_selects(in_memory_session) as statements:
        results = repo.list_created_since(now - timedelta(days=1))
        assert len(results) == 1
        assert results[0].id == "doc-recent"
        assert len(results[0].passages) == 2

    select_statements = [stmt for stmt in statements if stmt.lstrip().upper().startswith("SELECT")]
    assert len(select_statements) <= 2
