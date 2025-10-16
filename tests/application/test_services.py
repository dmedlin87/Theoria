import pytest

from theo.application.services import ApplicationContainer
from theo.domain import Document, DocumentId, DocumentMetadata


@pytest.fixture
def sample_document():
    return Document(
        id=DocumentId("doc-123"),
        metadata=DocumentMetadata(title="Test Doc", source="UnitTest"),
        scripture_refs=("John.3.16",),
    )


def test_bind_command_returns_ingest_callable(sample_document):
    calls = []

    def ingest(document: Document) -> DocumentId:
        calls.append(document)
        return DocumentId("doc-123")

    container = ApplicationContainer(
        ingest_document=ingest,
        retire_document=lambda _doc_id: None,
        get_document=lambda _doc_id: None,
        list_documents=lambda *, limit=20: [],
        research_service_factory=lambda session: session,
    )

    command = container.bind_command()
    assert command is ingest

    result = command(sample_document)

    assert result == DocumentId("doc-123")
    assert calls == [sample_document]


def test_bind_retire_returns_retire_callable():
    calls: list[DocumentId] = []

    def retire(document_id: DocumentId) -> None:
        calls.append(document_id)

    container = ApplicationContainer(
        ingest_document=lambda _doc: DocumentId("unused"),
        retire_document=retire,
        get_document=lambda _doc_id: None,
        list_documents=lambda *, limit=20: [],
        research_service_factory=lambda session: session,
    )

    retire_adapter = container.bind_retire()
    assert retire_adapter is retire

    retire_adapter(DocumentId("doc-321"))

    assert calls == [DocumentId("doc-321")]


def test_bind_get_returns_get_callable(sample_document):
    calls: list[DocumentId] = []

    def get_document(document_id: DocumentId) -> Document | None:
        calls.append(document_id)
        return sample_document

    container = ApplicationContainer(
        ingest_document=lambda _doc: DocumentId("unused"),
        retire_document=lambda _doc_id: None,
        get_document=get_document,
        list_documents=lambda *, limit=20: [],
        research_service_factory=lambda session: session,
    )

    getter = container.bind_get()
    assert getter is get_document

    result = getter(DocumentId("doc-123"))

    assert result is sample_document
    assert calls == [DocumentId("doc-123")]


def test_bind_list_wraps_limit_argument(sample_document):
    limits: list[int] = []

    def list_documents(*, limit: int = 20) -> list[Document]:
        limits.append(limit)
        return [sample_document]

    container = ApplicationContainer(
        ingest_document=lambda _doc: DocumentId("unused"),
        retire_document=lambda _doc_id: None,
        get_document=lambda _doc_id: None,
        list_documents=list_documents,
        research_service_factory=lambda session: session,
    )

    list_adapter = container.bind_list()

    assert list_adapter() == [sample_document]
    assert limits[-1] == 20

    assert list_adapter(5) == [sample_document]
    assert limits[-1] == 5


def test_get_research_service_uses_factory():
    class DummyService:
        pass

    observed_sessions: list[object] = []
    expected_service = DummyService()

    def factory(session: object) -> DummyService:
        observed_sessions.append(session)
        return expected_service

    container = ApplicationContainer(
        ingest_document=lambda _doc: DocumentId("unused"),
        retire_document=lambda _doc_id: None,
        get_document=lambda _doc_id: None,
        list_documents=lambda *, limit=20: [],
        research_service_factory=factory,
    )

    session = object()
    service = container.get_research_service(session)

    assert service is expected_service
    assert observed_sessions == [session]
