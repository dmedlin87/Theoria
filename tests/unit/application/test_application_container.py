"""Tests for the :mod:`theo.application.services` module."""
from __future__ import annotations

from theo.application.services import ApplicationContainer
from theo.domain import Document, DocumentId, DocumentMetadata


def _make_document(identifier: str = "doc-1") -> Document:
    return Document(
        id=DocumentId(identifier),
        metadata=DocumentMetadata(title="Title", source="Source"),
        scripture_refs=(),
    )


def test_bind_command_delegates_to_ingest_callable():
    captured: dict[str, object] = {}

    def fake_ingest(document: Document) -> DocumentId:
        captured["document"] = document
        return DocumentId("ingested")

    container = ApplicationContainer(
        ingest_document=fake_ingest,
        retire_document=lambda _doc_id: None,
        get_document=lambda _doc_id: None,
        list_documents=lambda *, limit: [],
        research_service_factory=lambda _session: object(),
    )

    doc = _make_document()
    command = container.bind_command()

    assert command(doc) == DocumentId("ingested")
    assert captured["document"] is doc


def test_bind_retire_returns_original_callable():
    captured: dict[str, DocumentId] = {}

    def fake_retire(doc_id: DocumentId) -> None:
        captured["doc_id"] = doc_id

    container = ApplicationContainer(
        ingest_document=lambda document: DocumentId("noop"),
        retire_document=fake_retire,
        get_document=lambda _doc_id: None,
        list_documents=lambda *, limit: [],
        research_service_factory=lambda _session: object(),
    )

    retire = container.bind_retire()
    retire(DocumentId("doc-99"))

    assert captured["doc_id"] == DocumentId("doc-99")


def test_bind_get_returns_original_callable():
    document = _make_document("doc-55")

    def fake_get(doc_id: DocumentId) -> Document | None:
        return document if doc_id == document.id else None

    container = ApplicationContainer(
        ingest_document=lambda document: DocumentId("noop"),
        retire_document=lambda _doc_id: None,
        get_document=fake_get,
        list_documents=lambda *, limit: [],
        research_service_factory=lambda _session: object(),
    )

    get = container.bind_get()

    assert get(DocumentId("doc-55")) is document
    assert get(DocumentId("doc-unknown")) is None


def test_bind_list_wraps_limit_argument():
    observed_limits: list[int] = []

    def fake_list(*, limit: int) -> list[Document]:
        observed_limits.append(limit)
        return []

    container = ApplicationContainer(
        ingest_document=lambda document: DocumentId("noop"),
        retire_document=lambda _doc_id: None,
        get_document=lambda _doc_id: None,
        list_documents=fake_list,
        research_service_factory=lambda _session: object(),
    )

    list_runner = container.bind_list()

    assert list_runner() == []
    assert list_runner(limit=5) == []
    assert observed_limits == [20, 5]


def test_get_research_service_uses_configured_factory():
    class _Session:
        pass

    session = _Session()
    marker = object()

    def fake_factory(bound_session: _Session) -> object:
        assert bound_session is session
        return marker

    container = ApplicationContainer(
        ingest_document=lambda document: DocumentId("noop"),
        retire_document=lambda _doc_id: None,
        get_document=lambda _doc_id: None,
        list_documents=lambda *, limit: [],
        research_service_factory=fake_factory,
    )

    assert container.get_research_service(session) is marker
