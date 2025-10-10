from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from theo.services.api.app.case_builder import sync_case_objects_for_document
from theo.services.api.app.core import settings as settings_module
from theo.services.api.app.core.database import Base
from theo.services.api.app.db.models import (
    CaseObject,
    CaseSource,
    Document,
    Passage,
)
from theo.services.api.app.ingest.chunking import Chunk
from theo.services.api.app.ingest.persistence import (
    PersistenceDependencies,
    persist_text_document,
)


@pytest.fixture()
def sqlite_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path}/case_builder.sqlite")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _reset_settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    missing_keys = {"CASE_BUILDER_ENABLED"} - set(env)
    for key in missing_keys:
        monkeypatch.delenv(key, raising=False)
    settings_module.get_settings.cache_clear()


def test_sync_case_objects_creates_records_when_enabled(
    sqlite_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_settings(monkeypatch, CASE_BUILDER_ENABLED="true")
    settings = settings_module.get_settings()

    document = Document(title="Doc", source_type="txt")
    sqlite_session.add(document)
    sqlite_session.flush()

    passage = Passage(
        document_id=document.id,
        text="In the beginning",
        raw_text="In the beginning",
        tokens=3,
        osis_ref="Gen.1.1",
        meta={"osis_refs_all": ["Gen.1.1"], "stability": 0.75},
    )
    sqlite_session.add(passage)
    sqlite_session.flush()

    created = sync_case_objects_for_document(
        sqlite_session, document=document, passages=[passage], settings=settings
    )

    assert len(created) == 1
    source = sqlite_session.query(CaseSource).one()
    case_object = sqlite_session.query(CaseObject).one()
    assert case_object.source_id == source.id
    assert case_object.osis_ranges == ["Gen.1.1"]
    assert pytest.approx(case_object.stability or 0.0, rel=1e-6) == pytest.approx(0.75)


def test_sync_case_objects_noop_when_disabled(
    sqlite_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_settings(monkeypatch, CASE_BUILDER_ENABLED="false")
    settings = settings_module.get_settings()

    document = Document(title="Doc", source_type="txt")
    sqlite_session.add(document)
    sqlite_session.flush()

    passage = Passage(
        document_id=document.id,
        text="Example",
        raw_text="Example",
        tokens=1,
    )
    sqlite_session.add(passage)
    sqlite_session.flush()

    created = sync_case_objects_for_document(
        sqlite_session, document=document, passages=[passage], settings=settings
    )

    assert created == []
    assert sqlite_session.query(CaseObject).count() == 0


class _DummyEmbeddingService:
    def __init__(self, dimension: int) -> None:
        self._dimension = dimension

    def embed(self, texts):  # type: ignore[no-untyped-def]
        return [[0.0] * self._dimension for _ in texts]


def test_persist_text_document_invokes_case_builder_sync(
    sqlite_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_settings(monkeypatch, CASE_BUILDER_ENABLED="true")
    settings = settings_module.get_settings()

    called = {}

    def _fake_sync(session, document, passages, settings):  # type: ignore[no-untyped-def]
        called["document_id"] = document.id
        called["passages"] = [p.id for p in passages]
        return []

    monkeypatch.setattr(
        "theo.services.api.app.case_builder.ingest.sync_case_objects_for_document",
        _fake_sync,
    )

    dependencies = PersistenceDependencies(
        embedding_service=_DummyEmbeddingService(settings.embedding_dim)
    )

    chunk = Chunk(text="Sample text", start_char=0, end_char=11, index=0)

    persist_text_document(
        sqlite_session,
        dependencies=dependencies,
        chunks=[chunk],
        parser="plain",
        parser_version="1.0.0",
        frontmatter={},
        settings=settings,
        sha256="case-builder-test",
        source_type="txt",
        title="Sample",
        source_url=None,
        text_content="Sample text",
    )

    assert "document_id" in called
    assert len(called["passages"]) == 1


def test_persist_text_document_does_not_call_case_builder_when_disabled(
    sqlite_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_settings(monkeypatch, CASE_BUILDER_ENABLED="false")
    settings = settings_module.get_settings()

    def _fail_sync(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("case builder sync should not run")

    monkeypatch.setattr(
        "theo.services.api.app.case_builder.ingest.sync_case_objects_for_document",
        _fail_sync,
    )

    dependencies = PersistenceDependencies(
        embedding_service=_DummyEmbeddingService(settings.embedding_dim)
    )
    chunk = Chunk(text="Sample text", start_char=0, end_char=11, index=0)

    persist_text_document(
        sqlite_session,
        dependencies=dependencies,
        chunks=[chunk],
        parser="plain",
        parser_version="1.0.0",
        frontmatter={},
        settings=settings,
        sha256="case-builder-test-disabled",
        source_type="txt",
        title="Sample",
        source_url=None,
        text_content="Sample text",
    )
