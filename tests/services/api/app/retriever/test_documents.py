from __future__ import annotations

from datetime import UTC, datetime

import pytest

try:  # pragma: no cover - optional dependency for lightweight environments
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool
except ModuleNotFoundError:  # pragma: no cover - gracefully skip when SQLAlchemy missing
    pytest.skip("sqlalchemy not installed", allow_module_level=True)
except ImportError:  # pragma: no cover - minimal stubs without pool support
    pytest.skip("sqlalchemy pool utilities unavailable", allow_module_level=True)

from theo.infrastructure.api.app.models.documents import (
    DocumentAnnotationCreate,
    DocumentAnnotationResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentPassagesResponse,
    DocumentUpdateRequest,
)
from theo.infrastructure.api.app.persistence_models import (
    Base,
    Document,
    DocumentAnnotation,
    Passage,
)
from theo.infrastructure.api.app.retriever import documents


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
def session(engine) -> Session:
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)


@pytest.fixture(autouse=True)
def _support_order_by_on_selectinload(monkeypatch):
    from sqlalchemy.orm.strategy_options import Load

    if hasattr(Load, "order_by"):
        return

    monkeypatch.setattr(
        Load,
        "order_by",
        lambda self, *args, **kwargs: self,
        raising=False,
    )


def _add_document(session: Session, **overrides) -> Document:
    timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    document = Document(
        id=overrides.get("id", "doc-1"),
        title=overrides.get("title", "Grace and Practice"),
        source_type=overrides.get("source_type", "sermon"),
        collection=overrides.get("collection", "research"),
        authors=overrides.get("authors", ["Alice"]),
        doi=overrides.get("doi"),
        venue=overrides.get("venue"),
        year=overrides.get("year", 2024),
        bib_json=overrides.get("bib_json", {"primary_topic": "Grace"}),
        topics=overrides.get("topics", ["Grace"]),
        theological_tradition=overrides.get("theological_tradition", "Catholic"),
        topic_domains=overrides.get("topic_domains", ["Doctrine"]),
        provenance_score=overrides.get("provenance_score", 7),
        created_at=overrides.get("created_at", timestamp),
        updated_at=overrides.get("updated_at", timestamp),
    )
    session.add(document)
    session.flush()
    return document


def _add_passage(session: Session, document_id: str, **overrides) -> Passage:
    passage = Passage(
        id=overrides.get("id", "p-1"),
        document_id=document_id,
        text=overrides.get("text", "Grace teaches love"),
        raw_text=overrides.get("raw_text", "Grace teaches love"),
        page_no=overrides.get("page_no", 1),
        start_char=overrides.get("start_char", 0),
        end_char=overrides.get("end_char", 10),
        osis_ref=overrides.get("osis_ref"),
        meta=overrides.get("meta", {"section": "intro"}),
    )
    session.add(passage)
    session.flush()
    return passage


def _add_annotation(session: Session, document_id: str, body: str, *, created_at: datetime | None = None) -> DocumentAnnotation:
    created = created_at or datetime(2024, 1, 1, tzinfo=UTC)
    annotation = DocumentAnnotation(
        document_id=document_id,
        body=body,
        created_at=created,
        updated_at=created,
    )
    session.add(annotation)
    session.flush()
    return annotation


def test_list_documents_returns_paginated_summary(session: Session):
    old = _add_document(session, id="doc-old", created_at=datetime(2023, 1, 1, tzinfo=UTC))
    recent = _add_document(session, id="doc-recent", created_at=datetime(2024, 5, 1, tzinfo=UTC))

    response = documents.list_documents(session, limit=1, offset=0)

    assert isinstance(response, DocumentListResponse)
    assert response.total == 2
    assert response.limit == 1
    assert response.items[0].id == recent.id


def test_get_document_includes_passages_and_annotations(session: Session):
    document = _add_document(session, id="doc-detail")
    first = _add_passage(session, document.id, id="p-1", page_no=2, start_char=5)
    second = _add_passage(session, document.id, id="p-0", page_no=1, start_char=1)
    _add_annotation(session, document.id, body='{ "text": "Insight" }')

    detail = documents.get_document(session, document.id)

    assert isinstance(detail, DocumentDetailResponse)
    assert {passage.id for passage in detail.passages} == {first.id, second.id}
    assert detail.annotations[0].body == "Insight"
    assert detail.metadata == {"primary_topic": "Grace"}


def test_get_document_enriches_passages_with_biblical_meta(session: Session):
    document = _add_document(session, id="doc-biblical")
    meta = {
        "biblical_text": {
            "reference": {
                "book": "Genesis",
                "chapter": 1,
                "verse": 1,
                "book_id": "gen",
                "osis_id": "Gen.1.1",
            },
            "language": "hebrew",
            "text": {
                "raw": "בְּרֵאשִׁית בָּרָא אֱלֹהִים",
                "normalized": "בראשית ברא אלהים",
            },
        }
    }
    _add_passage(
        session,
        document.id,
        id="p-biblical",
        text="בראשית ברא אלהים",
        raw_text="בְּרֵאשִׁית בָּרָא אֱלֹהִים",
        osis_ref="Gen.1.1",
        meta=meta,
    )

    detail = documents.get_document(session, document.id)
    passage_lookup = {item.id: item for item in detail.passages}
    verse_passage = passage_lookup["p-biblical"]

    assert verse_passage.text == "בראשית ברא אלהים"
    assert verse_passage.meta is not None
    assert "biblical_text" in verse_passage.meta
    assert verse_passage.meta["biblical_text"]["reference"]["osis_id"] == "Gen.1.1"


def test_get_document_missing_raises_key_error(session: Session):
    with pytest.raises(KeyError):
        documents.get_document(session, "missing")


def test_get_document_passages_paginates_sorted_results(session: Session):
    document = _add_document(session, id="doc-passages")
    _add_passage(session, document.id, id="p-1", page_no=1, start_char=0)
    _add_passage(session, document.id, id="p-2", page_no=2, start_char=0)
    _add_passage(session, document.id, id="p-3", page_no=3, start_char=0)

    page = documents.get_document_passages(session, document.id, limit=2, offset=1)

    assert isinstance(page, DocumentPassagesResponse)
    assert page.total == 3
    assert [passage.id for passage in page.passages] == ["p-2", "p-3"]


def test_get_document_passages_missing_document(session: Session):
    with pytest.raises(KeyError):
        documents.get_document_passages(session, "missing")


def test_get_latest_digest_document_returns_detail(session: Session):
    digest_old = _add_document(session, id="digest-old", source_type="digest", created_at=datetime(2024, 1, 1, tzinfo=UTC))
    digest_new = _add_document(session, id="digest-new", source_type="digest", created_at=datetime(2024, 6, 1, tzinfo=UTC))
    _add_passage(session, digest_new.id, id="digest-pass")

    detail = documents.get_latest_digest_document(session)

    assert detail.id == digest_new.id
    assert isinstance(detail, DocumentDetailResponse)


def test_get_latest_digest_document_raises_when_missing(session: Session):
    session.query(Document).delete()
    session.flush()

    with pytest.raises(KeyError):
        documents.get_latest_digest_document(session)


def test_update_document_applies_partial_updates(session: Session):
    document = _add_document(session, id="doc-update", title="Old Title", collection="old", authors=["Alice"])  # type: ignore[arg-type]
    payload = DocumentUpdateRequest(title="New Title", collection="", authors=None, meta={"primary_topic": "Hope"})

    updated = documents.update_document(session, document.id, payload)

    assert updated.title == "New Title"
    assert updated.collection is None
    assert updated.authors == ["Alice"]
    refreshed = session.get(Document, document.id)
    assert refreshed.bib_json == {"primary_topic": "Hope"}


def test_list_annotations_returns_sorted_entries(session: Session):
    document = _add_document(session, id="doc-annotations")
    first = _add_annotation(session, document.id, body="{\"text\": \"First\"}", created_at=datetime(2024, 1, 1, tzinfo=UTC))
    second = _add_annotation(session, document.id, body="{\"text\": \"Second\"}", created_at=datetime(2024, 2, 1, tzinfo=UTC))

    annotations = documents.list_annotations(session, document.id)

    assert [item.body for item in annotations] == ["First", "Second"]
    assert isinstance(annotations[0], DocumentAnnotationResponse)


def test_create_annotation_persists_structured_body(monkeypatch, session: Session):
    document = _add_document(session, id="doc-create")
    payload = DocumentAnnotationCreate(type="note", text="  Example  ", passage_ids=["p-1", "p-1"])

    recorded: dict[str, tuple] = {}

    def _record_case_sync(session: Session, *, document: Document, annotation: DocumentAnnotation):
        recorded["called"] = (document.id, annotation.id)

    monkeypatch.setattr(documents, "sync_annotation_case_object", _record_case_sync)

    response = documents.create_annotation(session, document.id, payload)

    assert response.body == "Example"
    assert response.passage_ids == ["p-1"]
    assert recorded["called"][0] == document.id
    stored = session.get(DocumentAnnotation, response.id)
    assert stored.body.startswith("{")


def test_create_annotation_missing_document(monkeypatch, session: Session):
    payload = DocumentAnnotationCreate(type="note", text="Example")

    with pytest.raises(KeyError):
        documents.create_annotation(session, "missing", payload)


def test_delete_annotation_removes_row(session: Session):
    document = _add_document(session, id="doc-delete")
    annotation = _add_annotation(session, document.id, body="Legacy note")

    documents.delete_annotation(session, document.id, annotation.id)

    assert session.get(DocumentAnnotation, annotation.id) is None


def test_delete_annotation_missing_document_or_annotation(session: Session):
    document = _add_document(session, id="doc-delete-missing")
    annotation = _add_annotation(session, document.id, body="note")

    with pytest.raises(KeyError):
        documents.delete_annotation(session, "missing", annotation.id)

    with pytest.raises(KeyError):
        documents.delete_annotation(session, document.id, "missing")

