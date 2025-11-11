"""Unit tests for the SQLAlchemy document repository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from sqlalchemy.orm import Session

from theo.adapters.persistence.document_repository import SQLAlchemyDocumentRepository
from theo.adapters.persistence.models import Document, Passage, _PREFETCHED_EMBEDDING_ATTR

pytestmark = pytest.mark.db


class RecordingEmbeddingService:
    """Collect invocations to ``get_many`` and return preset embeddings."""

    def __init__(self, embeddings: dict[str, list[float] | None] | None = None) -> None:
        self.embeddings = embeddings or {}
        self.calls: list[tuple[str, ...]] = []

    def get_many(self, passage_ids: list[str]) -> dict[str, list[float] | None]:
        self.calls.append(tuple(passage_ids))
        return {identifier: self.embeddings.get(identifier) for identifier in passage_ids}


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


def test_get_by_id_returns_prefetched_passages(session: Session):
    service = RecordingEmbeddingService(
        {
            "pass-1": [0.1, 0.2],
            "pass-2": [0.3, 0.4],
        }
    )
    repo = SQLAlchemyDocumentRepository(session, embedding_service=service)

    document = Document(
        id="doc-10",
        collection="user-123",
        title="Example",
        abstract=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(document)
    session.flush()
    session.add_all(
        [
            Passage(id="pass-1", document_id=document.id, text="a", embedding=[0.9]),
            Passage(id="pass-2", document_id=document.id, text="b", embedding=None),
        ]
    )
    session.flush()

    dto = repo.get_by_id(document.id)

    assert set(service.calls[0]) == {"pass-1", "pass-2"}
    assert dto is not None
    assert {p.id: p.embedding for p in dto.passages} == {
        "pass-1": [0.1, 0.2],
        "pass-2": [0.3, 0.4],
    }


def test_get_by_id_returns_none_when_missing(session: Session):
    repo = SQLAlchemyDocumentRepository(session)

    assert repo.get_by_id("missing") is None


def test_list_summaries_honors_limit(session: Session):
    repo = SQLAlchemyDocumentRepository(session)
    now = datetime.now(UTC)
    documents = [
        Document(id=f"doc-{idx}", collection="user-limit", title=f"Doc {idx}", created_at=now, updated_at=now)
        for idx in range(3)
    ]
    documents.append(
        Document(id="doc-other", collection="other-user", title="Hidden", created_at=now, updated_at=now)
    )
    session.add_all(documents)
    session.flush()

    summaries = repo.list_summaries("user-limit", limit=2)

    assert len(summaries) == 2
    assert all(summary.collection == "user-limit" for summary in summaries)


def test_list_created_since_filters_and_orders_results(session: Session):
    service = RecordingEmbeddingService({"p-fast": [0.1], "p-late": [0.2]})
    repo = SQLAlchemyDocumentRepository(session, embedding_service=service)
    base = datetime.now(UTC) - timedelta(days=1)

    docs = [
        Document(id="doc-old", collection="user", title="Old", created_at=base - timedelta(days=1), updated_at=base),
        Document(id="doc-fast", collection="user", title="Fast", created_at=base + timedelta(minutes=5), updated_at=base),
        Document(id="doc-late", collection="user", title="Late", created_at=base + timedelta(hours=1), updated_at=base),
    ]
    session.add_all(docs)
    session.flush()
    session.add_all(
        [
            Passage(id="p-fast", document_id="doc-fast", text="fast", embedding=None),
            Passage(id="p-late", document_id="doc-late", text="late", embedding=None),
        ]
    )
    session.flush()

    results = repo.list_created_since(base, limit=2)

    assert [doc.id for doc in results] == ["doc-fast", "doc-late"]
    # Each qualifying document should have triggered an embedding prefetch.
    assert service.calls == [("p-fast",), ("p-late",)]


def test_prefetch_embeddings_caches_results_on_passages(session: Session):
    service = RecordingEmbeddingService({"a": [0.1], "b": [0.2]})
    repo = SQLAlchemyDocumentRepository(session, embedding_service=service)
    passages = [
        SimpleNamespace(id="a"),
        SimpleNamespace(id="b"),
        SimpleNamespace(id="a"),
    ]

    mapping = repo._prefetch_embeddings(passages)  # type: ignore[arg-type]

    assert mapping == {"a": [0.1], "b": [0.2]}
    assert service.calls == [("a", "b")]
    assert all(hasattr(p, _PREFETCHED_EMBEDDING_ATTR) for p in passages)


def test_resolve_embedding_prefers_cached_value_and_falls_back(session: Session):
    repo = SQLAlchemyDocumentRepository(session, embedding_service=RecordingEmbeddingService())
    cached = SimpleNamespace(id="cached")
    setattr(cached, _PREFETCHED_EMBEDDING_ATTR, [0.9])

    result_cached = repo._resolve_embedding(cached, {"cached": [0.1]})  # type: ignore[arg-type]
    assert result_cached == [0.9]

    to_cache = SimpleNamespace(id="new")
    result_new = repo._resolve_embedding(to_cache, {"new": [0.2]})  # type: ignore[arg-type]
    assert result_new == [0.2]
    assert getattr(to_cache, _PREFETCHED_EMBEDDING_ATTR) == [0.2]

    fallback = SimpleNamespace(id=None, embedding=[1.2])
    assert repo._resolve_embedding(fallback, {}) == [1.2]  # type: ignore[arg-type]
