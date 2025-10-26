from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from sqlalchemy.orm import Session, sessionmaker

from theo.application.facades.database import Base, configure_engine, get_engine


@pytest.fixture(scope="module")
def pipeline_engine(tmp_path_factory: pytest.TempPathFactory):
    """Provision a shared SQLite database for pipeline ingestion tests."""

    db_dir = tmp_path_factory.mktemp("pipeline-db")
    db_path = Path(db_dir) / "pipeline.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


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


@pytest.fixture(autouse=True)
def _stub_pythonbible(monkeypatch: pytest.MonkeyPatch):
    """Replace heavy pythonbible lookups with a lightweight stub during tests."""

    try:
        from theo.services.api.app.ingest import osis as ingest_osis
    except ModuleNotFoundError:  # pragma: no cover - dependency not installed
        yield
        return

    pb_module = getattr(ingest_osis, "pb", None)
    if pb_module is None:
        yield
        return

    monkeypatch.setattr(pb_module, "get_references", lambda _text: [], raising=False)
    monkeypatch.setattr(pb_module, "get_bible_book_id", lambda *_args, **_kwargs: None, raising=False)
    yield
