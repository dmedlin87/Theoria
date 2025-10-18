"""Unit tests for the SQLAlchemy document repository."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from theo.adapters.persistence.document_repository import SQLAlchemyDocumentRepository
from theo.adapters.persistence.models import Base, Document, Passage


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def test_list_with_embeddings_averages_vectors(session: Session):
    repo = SQLAlchemyDocumentRepository(session)

    primary = Document(
        id="doc-1",
        collection="user-1",
        title=None,
        abstract="Exploring themes.",
        topics=["  Grace  ", {"label": " Service "}, ""],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    other = Document(
        id="doc-2",
        collection="user-2",
        title="Other",
        abstract=None,
        topics=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add_all([primary, other])
    session.flush()

    session.add_all(
        [
            Passage(
                document_id="doc-1",
                text="content",
                embedding=[0.2, 0.4, 0.6],
                osis_verse_ids=[5, 2, 5],
            ),
            Passage(
                document_id="doc-1",
                text="content",
                embedding=[float("nan"), 0.8, 0.9],
                osis_verse_ids=[3],
            ),
            Passage(
                document_id="doc-1",
                text="content",
                embedding=[0.0, 0.1, 0.2],
                osis_verse_ids=[7, "not-an-int"],
            ),
            Passage(
                document_id="doc-2",
                text="content",
                embedding=None,
                osis_verse_ids=[1],
            ),
        ]
    )
    session.flush()

    results = repo.list_with_embeddings("user-1")

    assert len(results) == 1
    embedding = np.mean([[0.2, 0.4, 0.6], [0.0, 0.1, 0.2]], axis=0).tolist()
    document = results[0]
    assert document.document_id == "doc-1"
    assert document.title == "Untitled Document"
    assert document.embedding == pytest.approx(embedding)
    assert document.topics == ["Grace", "Service"]
    assert document.verse_ids == [2, 3, 5, 7]
    assert document.metadata == {"keywords": ["Grace", "Service"], "documentId": "doc-1"}


def test_list_with_embeddings_uses_selectinload():
    mock_session = Mock()
    mock_session.scalars.return_value.all.return_value = []

    repo = SQLAlchemyDocumentRepository(mock_session)
    repo.list_with_embeddings("someone")

    stmt = mock_session.scalars.call_args[0][0]
    assert stmt._with_options  # ensures eager loading configured
