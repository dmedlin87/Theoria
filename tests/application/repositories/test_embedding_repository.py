"""Tests for the SQLAlchemy passage embedding repository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.adapters.persistence.embedding_repository import (
    SQLAlchemyPassageEmbeddingRepository,
)
from theo.adapters.persistence.models import Document, Passage, PassageEmbedding
from theo.application.repositories.embedding_repository import EmbeddingUpdate

pytestmark = pytest.mark.db


def _document(identifier: str, *, timestamp: datetime) -> Document:
    return Document(
        id=identifier,
        collection="embedding-tests",
        title=identifier,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _passage(identifier: str, document_id: str, *, text: str) -> Passage:
    return Passage(id=identifier, document_id=document_id, text=text)


def test_count_candidates_respects_flags(session: Session) -> None:
    repo = SQLAlchemyPassageEmbeddingRepository(session)
    now = datetime.now(UTC)
    doc_recent = _document("doc-recent", timestamp=now)
    doc_old = _document("doc-old", timestamp=now - timedelta(days=2))
    session.add_all([doc_recent, doc_old])
    session.flush()
    needs_recent = _passage("pass-recent", doc_recent.id, text="recent")
    needs_old = _passage("pass-old", doc_old.id, text="old")
    embedded = _passage("pass-embedded", doc_recent.id, text="embedded")
    session.add_all([needs_recent, needs_old, embedded])
    session.flush()
    session.add(PassageEmbedding(passage_id=embedded.id, embedding=[0.1, 0.1, 0.1]))
    session.flush()

    assert repo.count_candidates(fast=True, changed_since=None, ids=None) == 2
    assert repo.count_candidates(
        fast=True, changed_since=now - timedelta(hours=1), ids=None
    ) == 1
    assert (
        repo.count_candidates(fast=False, changed_since=None, ids=[needs_old.id]) == 1
    )


def test_existing_ids_returns_subset(session: Session) -> None:
    repo = SQLAlchemyPassageEmbeddingRepository(session)
    timestamp = datetime.now(UTC)
    doc = _document("doc-existing", timestamp=timestamp)
    session.add(doc)
    session.flush()
    session.add_all(
        [
            _passage("p1", doc.id, text="one"),
            _passage("p2", doc.id, text="two"),
        ]
    )
    session.flush()

    assert repo.existing_ids(["p1", "missing"]) == {"p1"}


def test_iter_candidates_includes_document_timestamp(session: Session) -> None:
    repo = SQLAlchemyPassageEmbeddingRepository(session)
    timestamp = datetime.now(UTC)
    doc = _document("doc-candidates", timestamp=timestamp)
    session.add(doc)
    session.flush()
    first = _passage("a", doc.id, text="alpha")
    second = _passage("b", doc.id, text="beta")
    session.add_all([first, second])
    session.flush()
    session.add(PassageEmbedding(passage_id=second.id, embedding=[0.5, 0.0, 0.5]))
    session.flush()

    candidates = list(
        repo.iter_candidates(
            fast=False,
            changed_since=timestamp - timedelta(minutes=1),
            ids=None,
            batch_size=1,
        )
    )

    assert [candidate.id for candidate in candidates] == ["a", "b"]
    for candidate in candidates:
        assert candidate.document_updated_at is not None
        observed = candidate.document_updated_at
        cutoff_ts = (timestamp - timedelta(minutes=1)).timestamp()
        if observed.tzinfo is None:
            observed_ts = observed.replace(tzinfo=UTC).timestamp()
        else:
            observed_ts = observed.timestamp()
        assert observed_ts >= cutoff_ts
    assert candidates[0].embedding is None
    assert list(candidates[1].embedding or []) == [0.5, 0.0, 0.5]


def test_iter_candidates_respects_ids_and_fast_flag(session: Session) -> None:
    repo = SQLAlchemyPassageEmbeddingRepository(session)
    timestamp = datetime.now(UTC)
    doc = _document("doc-filtered", timestamp=timestamp)
    session.add(doc)
    session.flush()
    needs = _passage("needs", doc.id, text="missing")
    embedded = _passage("has", doc.id, text="existing")
    session.add_all([needs, embedded])
    session.flush()
    session.add(PassageEmbedding(passage_id=embedded.id, embedding=[0.7, 0.7, 0.7]))
    session.flush()

    filtered_candidates = list(
        repo.iter_candidates(
            fast=False,
            changed_since=None,
            ids=[needs.id],
            batch_size=5,
        )
    )

    assert [candidate.id for candidate in filtered_candidates] == [needs.id]


def test_build_filters_handles_fast_and_changed_since(session: Session) -> None:
    repo = SQLAlchemyPassageEmbeddingRepository(session)
    cutoff = datetime.now(UTC)

    filters, join_document = repo._build_filters(
        fast=True,
        changed_since=cutoff,
        ids=["a", "b"],
    )

    assert join_document is True
    assert len(filters) == 3

    fast_only_filters, join_document_fast_only = repo._build_filters(
        fast=True,
        changed_since=None,
        ids=None,
    )
    assert join_document_fast_only is False
    assert len(fast_only_filters) == 1


def test_update_embeddings_replaces_existing_vectors(session: Session) -> None:
    repo = SQLAlchemyPassageEmbeddingRepository(session)
    timestamp = datetime.now(UTC)
    doc = _document("doc-update", timestamp=timestamp)
    session.add(doc)
    session.flush()
    existing = _passage("existing", doc.id, text="existing passage")
    fresh = _passage("fresh", doc.id, text="fresh passage")
    session.add_all([existing, fresh])
    session.flush()
    session.add(PassageEmbedding(passage_id=existing.id, embedding=[1.0, 1.0, 1.0]))
    session.flush()

    repo.update_embeddings(
        [
            EmbeddingUpdate(id=existing.id, embedding=[0.2, 0.2, 0.2]),
            EmbeddingUpdate(id=fresh.id, embedding=[0.9, 0.1, 0.0]),
        ]
    )

    rows = session.execute(
        select(PassageEmbedding).order_by(PassageEmbedding.passage_id)
    ).scalars()
    payload = {row.passage_id: list(row.embedding) for row in rows}
    assert payload == {
        "existing": [0.2, 0.2, 0.2],
        "fresh": [0.9, 0.1, 0.0],
    }
