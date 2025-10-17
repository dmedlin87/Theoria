from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from theo.services.api.app.case_builder import sync_case_objects_for_document
from theo.application.facades import settings as settings_module
from theo.application.facades.database import Base
from theo.adapters.persistence.models import (
    CaseObject,
    CaseSource,
    Document,
    Passage,
    PassageVerse,
)
from theo.services.api.app.ingest.chunking import Chunk
from theo.services.api.app.ingest.osis import expand_osis_reference
from theo.services.api.app.ingest.persistence import persist_text_document, persist_transcript_document
from theo.services.api.app.ingest.stages import IngestContext, Instrumentation


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


def test_sync_case_objects_notifies_updates(
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

    notified_payloads: list[list[str]] = []

    def _fake_notify(session, object_ids, notify_settings):  # type: ignore[no-untyped-def]
        assert session is sqlite_session
        assert notify_settings is settings
        notified_payloads.append(list(object_ids))

    monkeypatch.setattr(
        "theo.services.api.app.case_builder.ingest._notify_new_objects",
        _fake_notify,
    )

    created = sync_case_objects_for_document(
        sqlite_session, document=document, passages=[passage], settings=settings
    )

    assert len(created) == 1
    assert notified_payloads == [[created[0].id]]

    # Mutate passage content so the CaseObject is updated on re-ingest.
    passage.text = "Updated beginning"
    passage.meta = {"osis_refs_all": ["Gen.1.1"], "stability": 0.9}
    sqlite_session.flush()

    notified_payloads.clear()

    second_created = sync_case_objects_for_document(
        sqlite_session, document=document, passages=[passage], settings=settings
    )

    assert second_created == []
    assert notified_payloads == [[created[0].id]]


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

    context = IngestContext(
        settings=settings,
        embedding_service=_DummyEmbeddingService(settings.embedding_dim),
        instrumentation=Instrumentation(span=None),
    )

    chunk = Chunk(text="Sample text", start_char=0, end_char=11, index=0)

    persist_text_document(
        sqlite_session,
        context=context,
        chunks=[chunk],
        parser="plain",
        parser_version="1.0.0",
        frontmatter={},
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

    context = IngestContext(
        settings=settings,
        embedding_service=_DummyEmbeddingService(settings.embedding_dim),
        instrumentation=Instrumentation(span=None),
    )
    chunk = Chunk(text="Sample text", start_char=0, end_char=11, index=0)

    persist_text_document(
        sqlite_session,
        context=context,
        chunks=[chunk],
        parser="plain",
        parser_version="1.0.0",
        frontmatter={},
        sha256="case-builder-test-disabled",
        source_type="txt",
        title="Sample",
        source_url=None,
        text_content="Sample text",
    )


def test_persist_text_document_creates_passage_verses(sqlite_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_settings(monkeypatch, CASE_BUILDER_ENABLED="false")
    settings = settings_module.get_settings()

    context = IngestContext(
        settings=settings,
        embedding_service=_DummyEmbeddingService(settings.embedding_dim),
        instrumentation=Instrumentation(span=None),
    )
    chunk = Chunk(text="Reference chunk", start_char=0, end_char=17, index=0)

    document = persist_text_document(
        sqlite_session,
        context=context,
        chunks=[chunk],
        parser="plain",
        parser_version="1.0.0",
        frontmatter={"osis_refs": ["John.3.16", "John.3.16-John.3.17"]},
        sha256="passage-verse-test",
        source_type="txt",
        title="Verse Test",
        source_url=None,
        text_content="Reference chunk",
    )

    passage = sqlite_session.query(Passage).filter_by(document_id=document.id).one()
    verse_rows = sqlite_session.query(PassageVerse).filter_by(passage_id=passage.id).all()
    expected_ids = sorted(set(expand_osis_reference("John.3.16-John.3.17")))
    assert sorted(row.verse_id for row in verse_rows) == expected_ids
    assert passage.osis_verse_ids == expected_ids


def test_persist_transcript_document_creates_passage_verses(sqlite_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_settings(monkeypatch, CASE_BUILDER_ENABLED="false")
    settings = settings_module.get_settings()

    context = IngestContext(
        settings=settings,
        embedding_service=_DummyEmbeddingService(settings.embedding_dim),
        instrumentation=Instrumentation(span=None),
    )
    chunk = Chunk(
        text="Transcript reference",
        t_start=0.0,
        t_end=5.0,
        start_char=0,
        end_char=len("Transcript reference"),
        index=0,
    )

    document = persist_transcript_document(
        sqlite_session,
        context=context,
        chunks=[chunk],
        parser="plain",
        parser_version="1.0.0",
        frontmatter={"osis_refs": ["John.3.16"]},
        sha256="transcript-verse-test",
        source_type="transcript",
        title="Transcript",
    )

    passage = sqlite_session.query(Passage).filter_by(document_id=document.id).one()
    verse_rows = sqlite_session.query(PassageVerse).filter_by(passage_id=passage.id).all()
    expected_ids = sorted(set(expand_osis_reference("John.3.16")))
    assert sorted(row.verse_id for row in verse_rows) == expected_ids
    assert passage.osis_verse_ids == expected_ids
