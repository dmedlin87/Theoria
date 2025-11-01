from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterator, Sequence

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from theo.adapters.persistence import Base
from theo.adapters.persistence.models import (
    CaseObject,
    CaseSource,
    Document,
    DocumentAnnotation,
    Passage,
)
from theo.application.facades.settings import get_settings
from theo.infrastructure.api.app.case_builder import ingest, sync


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = PROJECT_ROOT / "fixtures" / "case_builder"


@pytest.fixture(scope="module")
def sqlite_engine(tmp_path_factory: pytest.TempPathFactory):
    db_dir = tmp_path_factory.mktemp("case_builder_workflows")
    engine = create_engine(f"sqlite:///{db_dir}/case_builder.sqlite")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def sqlite_session(sqlite_engine) -> Iterator[Session]:
    connection = sqlite_engine.connect()
    transaction = connection.begin()
    TestingSession = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = TestingSession()
    session.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def enabled_case_builder():
    settings = get_settings()
    original_flag = settings.case_builder_enabled
    settings.case_builder_enabled = True
    try:
        yield settings
    finally:
        settings.case_builder_enabled = original_flag


def _load_fixture(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_ndjson(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                records.append(json.loads(text))
    return records


def _make_passage_from_object(document_id: str, idx: int, payload: dict) -> Passage:
    passage = Passage(
        id=f"passage-{idx}-{payload['id']}",
        document_id=document_id,
        text=payload.get("body") or payload.get("title") or "",
        raw_text=payload.get("body"),
        tokens=len((payload.get("body") or "").split()),
        meta={
            "osis_refs_all": payload.get("osis_ranges") or payload.get("meta", {}).get("osis_refs_all") or [],
            "stability": payload.get("stability"),
        },
    )
    embedding = payload.get("embedding")
    if embedding is not None:
        passage.embedding = list(embedding)
    return passage


class _StubEmbeddingService:
    def __init__(self, values: Sequence[Sequence[float]]):
        self._values = [list(vector) for vector in values]
        self.calls: list[Sequence[str]] = []

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        self.calls.append(tuple(texts))
        return self._values


def test_case_construction_matches_bundle_fixture(
    sqlite_session: Session,
    enabled_case_builder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _load_fixture(FIXTURE_DIR / "bundle_record.json")
    source = bundle["source"]
    objects = bundle["objects"]

    topics = source.get("meta", {}).get("topic")
    document = Document(
        id=source["document_id"],
        title="Bundle Evidence Roundup",
        authors=[source["author"]],
        collection=source["origin"],
        source_type=source["modality"],
        source_url=source["url"],
        year=source["year"],
        pub_date=date(2024, 5, 5),
        topics=[topics] if isinstance(topics, str) else topics,
    )
    sqlite_session.add(document)

    passages = [
        _make_passage_from_object(document.id, index, payload)
        for index, payload in enumerate(objects, start=1)
    ]
    for passage in passages:
        sqlite_session.add(passage)
    sqlite_session.flush()

    notify_calls: list[tuple[Sequence[str], str | None]] = []

    def _record_notifications(
        session: Session,
        object_ids: Sequence[str],
        settings,
        *,
        document_id: str | None = None,
    ) -> None:
        notify_calls.append((tuple(object_ids), document_id))

    monkeypatch.setattr(
        "theo.infrastructure.api.app.case_builder.ingest._notify_new_objects",
        _record_notifications,
    )

    created = ingest.sync_case_objects_for_document(
        sqlite_session,
        document=document,
        passages=passages,
        settings=enabled_case_builder,
    )

    assert len(created) == len(objects)
    assert notify_calls == [(tuple(obj.id for obj in created), document.id)]

    stored_source = (
        sqlite_session.query(CaseSource)
        .filter(CaseSource.document_id == document.id)
        .one()
    )
    stored_objects = (
        sqlite_session.query(CaseObject)
        .filter(CaseObject.document_id == document.id)
        .order_by(CaseObject.passage_id)
        .all()
    )

    assert stored_source.origin == source["origin"]
    assert stored_source.url == source["url"]
    assert stored_source.modality == source["modality"]

    assert len(stored_objects) == len(objects)

    for stored, fixture_object in zip(stored_objects, objects):
        assert stored.body == fixture_object["body"]
        expected_tags = fixture_object.get("tags") or []
        assert set(stored.tags or []) <= set(expected_tags)
        embedding = fixture_object.get("embedding")
        if embedding is not None:
            assert list(stored.embedding or []) == pytest.approx(embedding)
        else:
            assert stored.embedding is None

    empty_result = ingest.sync_case_objects_for_document(
        sqlite_session,
        document=document,
        passages=[],
        settings=enabled_case_builder,
    )
    assert empty_result == []


def test_passage_sync_deduplicates_and_notifies(
    sqlite_session: Session,
    enabled_case_builder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = _load_ndjson(FIXTURE_DIR / "collision_records.ndjson")
    first_record = records[0]
    source = first_record["source"]
    objects = first_record["objects"]

    document_id = source.get("document_id") or f"doc-{source['id']}"
    aggregated_topics = [
        tag
        for payload in objects
        for tag in payload.get("tags", [])
        if tag
    ]
    document = Document(
        id=document_id,
        title="Collision Case Study",
        authors=[source.get("author")] if source.get("author") else None,
        collection=source.get("origin"),
        source_type=source.get("modality"),
        source_url=source.get("url"),
        year=source.get("year"),
        pub_date=date(2024, 5, 3),
        topics=aggregated_topics,
    )
    sqlite_session.add(document)

    passages = [
        _make_passage_from_object(document.id, index, payload)
        for index, payload in enumerate(objects, start=1)
    ]
    for passage in passages:
        sqlite_session.add(passage)
    sqlite_session.flush()

    notify_calls: list[tuple[tuple[str | None, ...], str | None]] = []

    def _record_notifications(
        session: Session,
        case_object_ids: Sequence[str | None],
        *,
        document_id: str | None = None,
    ) -> None:
        assert session is sqlite_session
        notify_calls.append((tuple(case_object_ids), document_id))

    monkeypatch.setattr(
        sync,
        "emit_case_object_notifications",
        _record_notifications,
    )

    changed_ids = sync.sync_passages_case_objects(
        sqlite_session,
        document=document,
        passages=passages,
        frontmatter=source.get("meta"),
    )

    assert len(changed_ids) == len(passages)
    assert notify_calls == [(tuple(changed_ids), document.id)]

    sqlite_session.flush()
    initial_case_object_ids = {
        obj.id
        for obj in sqlite_session.query(CaseObject)
        .filter(CaseObject.document_id == document.id)
        .all()
    }
    expected_stability = (source.get("meta") or {}).get("stability")

    second_pass = sync.sync_passages_case_objects(
        sqlite_session,
        document=document,
        passages=passages,
        frontmatter=source.get("meta"),
    )

    assert set(second_pass) == initial_case_object_ids
    assert notify_calls[-1] == (tuple(second_pass), document.id)
    sqlite_session.flush()

    stored_objects = (
        sqlite_session.query(CaseObject)
        .filter(CaseObject.document_id == document.id)
        .order_by(CaseObject.passage_id)
        .all()
    )
    assert len(stored_objects) == len(passages)
    stored_source = (
        sqlite_session.query(CaseSource)
        .filter(CaseSource.document_id == document.id)
        .one()
    )
    assert stored_source.meta == source.get("meta")
    for passage, case_object in zip(passages, stored_objects):
        assert case_object.meta is not None
        assert case_object.meta["passage_id"] == passage.id
        assert "passage_meta" in case_object.meta
        if expected_stability is None:
            assert case_object.stability is None
        else:
            assert case_object.stability == pytest.approx(float(expected_stability))


def test_annotation_sync_generates_citation_case_object(
    sqlite_session: Session,
    enabled_case_builder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    convergence = _load_fixture(FIXTURE_DIR / "sample_convergence.json")
    source = convergence["source"]
    annotation_payload = next(
        obj for obj in convergence["objects"] if obj.get("annotation_id")
    )

    document = Document(
        id=source["document_id"],
        title=annotation_payload["title"],
        authors=[source.get("author")] if source.get("author") else None,
        collection=source.get("origin"),
        source_type=source.get("modality"),
        source_url=source.get("url"),
        pub_date=date(2024, 4, 28),
        topics=["rest"],
    )
    sqlite_session.add(document)
    sqlite_session.flush()

    annotation_created = datetime.fromisoformat(
        annotation_payload.get("created_at", "2024-05-01T12:05:00Z").replace("Z", "+00:00")
    )
    annotation = DocumentAnnotation(
        id=annotation_payload["annotation_id"],
        document_id=document.id,
        body=annotation_payload["body"] + "  ",
        created_at=annotation_created,
        updated_at=annotation_created,
    )
    sqlite_session.add(annotation)
    sqlite_session.flush()

    embedding_service = _StubEmbeddingService([[0.12, 0.34, -0.56]])
    monkeypatch.setattr(
        "theo.infrastructure.api.app.case_builder.sync.get_embedding_service",
        lambda: embedding_service,
    )

    notify_calls: list[tuple[tuple[str | None, ...], str | None]] = []

    def _record_case_notifications(
        session: Session,
        case_object_ids: Sequence[str | None],
        *,
        document_id: str | None = None,
    ) -> None:
        assert session is sqlite_session
        notify_calls.append((tuple(case_object_ids), document_id))

    monkeypatch.setattr(
        sync,
        "emit_case_object_notifications",
        _record_case_notifications,
    )

    sync.sync_annotation_case_object(
        sqlite_session,
        document=document,
        annotation=annotation,
    )

    assert embedding_service.calls == [(annotation.body.strip(),)]
    assert len(notify_calls) == 1
    notified_ids, notified_document = notify_calls[0]
    assert notified_document == document.id
    assert set(filter(None, notified_ids)) <= {
        obj.id
        for obj in sqlite_session.query(CaseObject)
        .filter(CaseObject.document_id == document.id)
        .all()
    }

    sqlite_session.flush()
    stored_case_object = (
        sqlite_session.query(CaseObject)
        .filter(CaseObject.annotation_id == annotation.id)
        .one()
    )
    assert stored_case_object.object_type == "annotation"
    assert stored_case_object.annotation_id == annotation.id
    assert stored_case_object.meta == {
        "annotation_created_at": annotation_created.replace(tzinfo=UTC).isoformat()
    }
    assert list(stored_case_object.embedding or []) == pytest.approx(
        [0.12, 0.34, -0.56]
    )

    annotation.body = "   "
    sqlite_session.flush()
    skipped = sync.sync_annotation_case_object(
        sqlite_session,
        document=document,
        annotation=annotation,
    )
    assert skipped is None
