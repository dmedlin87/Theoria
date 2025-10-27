"""Performance regression tests for the passage embedding cache."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from theo.adapters.persistence import Base
from theo.adapters.persistence.models import Document, Passage, PassageEmbedding
from theo.adapters.persistence.passage_embedding_store import (
    SQLAlchemyPassageEmbeddingStore,
)
from theo.application.embeddings.store import PassageEmbeddingService


@contextmanager
def _capture_queries(session: Session) -> Iterator[Callable[[], int]]:
    """Yield a callable returning the number of executed SQL statements."""

    count = 0
    engine = session.get_bind()

    def _before_execute(*_args, **_kwargs) -> None:  # type: ignore[no-untyped-def]
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", _before_execute)
    try:
        yield lambda: count
    finally:
        event.remove(engine, "before_cursor_execute", _before_execute)


@pytest.fixture()
def sqlite_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    session = SessionLocal()
    try:
        document = Document(id="doc-perf", title="Perf", collection="perf")
        session.add(document)
        session.flush()

        passage = Passage(
            document_id=document.id,
            text="cached",
            raw_text="cached",
            osis_ref="Gen.1.1",
        )
        session.add(passage)
        session.flush()
        session.add(
            PassageEmbedding(passage_id=passage.id, embedding=[1.0, 0.0, 0.5])
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.mark.performance
def test_service_avoids_duplicate_queries(sqlite_session: Session) -> None:
    store = SQLAlchemyPassageEmbeddingStore(sqlite_session)
    service = PassageEmbeddingService(store, cache_max_size=8)
    passage_id = sqlite_session.scalars(select(Passage.id)).first()
    assert passage_id is not None

    with _capture_queries(sqlite_session) as query_count:
        first = service.get(passage_id)
        assert first is not None and list(first) == [1.0, 0.0, 0.5]
        initial_queries = query_count()

    with _capture_queries(sqlite_session) as query_count:
        second = service.get(passage_id)
        assert second is not None and list(second) == [1.0, 0.0, 0.5]
        assert query_count() == 0

    assert initial_queries >= 1


@pytest.mark.performance
def test_bulk_fetch_populates_cache(sqlite_session: Session) -> None:
    store = SQLAlchemyPassageEmbeddingStore(sqlite_session)
    service = PassageEmbeddingService(store, cache_max_size=8)
    passage_ids = sqlite_session.execute(select(Passage.id)).scalars().all()
    assert passage_ids

    with _capture_queries(sqlite_session) as query_count:
        result = service.get_many(passage_ids)
        counts = query_count()

    assert counts >= 1
    assert all(result.get(identifier) is not None for identifier in passage_ids)

    with _capture_queries(sqlite_session) as query_count:
        cached = service.get_many(passage_ids)
        assert query_count() == 0

    assert cached == result
