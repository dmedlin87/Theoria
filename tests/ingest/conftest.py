from __future__ import annotations

from functools import lru_cache
from typing import Callable, Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from theo.application.facades.database import Base, configure_engine, get_engine
from tests.fixtures.pgvector import PGVectorDatabase, PGVectorClone


@pytest.fixture(scope="module")
def pipeline_engine(pgvector_db: PGVectorDatabase) -> Iterator[Engine]:
    """Provision a shared Postgres-backed engine for pipeline ingestion tests."""

    clone: PGVectorClone = pgvector_db.clone_database("ingest_pipeline")
    configure_engine(clone.url)
    engine = get_engine()
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        pgvector_db.drop_clone(clone)


@pytest.fixture
def pipeline_session_factory(pipeline_engine) -> Callable[[], Session]:
    """Yield a factory for sessions bound to a rolled-back transaction."""

    connection = pipeline_engine.connect()
    transaction = connection.begin()
    factory = sessionmaker(bind=connection)
    sessions: list[Session] = []

    def _factory() -> Session:
        session = factory()
        sessions.append(session)
        return session

    try:
        yield _factory
    finally:
        for session in sessions:
            session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def ingest_engine(pgvector_db: PGVectorDatabase) -> Iterator[Engine]:
    """Yield an isolated Postgres engine cloned from the seeded pgvector template."""

    clone: PGVectorClone = pgvector_db.clone_database("ingest_case")
    configure_engine(clone.url)
    engine = get_engine()
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        pgvector_db.drop_clone(clone)


@pytest.fixture(autouse=True)
def _stub_pythonbible(monkeypatch: pytest.MonkeyPatch):
    """Replace heavy pythonbible lookups with a lightweight stub during tests."""

    try:
        from theo.infrastructure.api.app.ingest import osis as ingest_osis
    except ModuleNotFoundError:  # pragma: no cover - dependency not installed
        yield
        return

    pb_module = getattr(ingest_osis, "pb", None)
    if pb_module is None:
        yield
        return

    get_references = getattr(pb_module, "get_references", None)
    get_bible_book_id = getattr(pb_module, "get_bible_book_id", None)
    if get_references is None or get_bible_book_id is None:
        yield
        return

    @lru_cache(maxsize=512)
    def _cached_get_references(text: str):
        try:
            return get_references(text)
        except Exception:
            return []

    @lru_cache(maxsize=128)
    def _cached_get_bible_book_id(*args, **kwargs):
        try:
            return get_bible_book_id(*args, **kwargs)
        except Exception:
            return None

    monkeypatch.setattr(pb_module, "get_references", _cached_get_references, raising=False)
    monkeypatch.setattr(pb_module, "get_bible_book_id", _cached_get_bible_book_id, raising=False)
    yield
