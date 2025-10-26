import pytest

from theo.application.interfaces import CommandService, QueryService, SessionProtocol
from theo.domain import Document, DocumentId, DocumentMetadata


class _FakeSession:
    """Minimal implementation satisfying :class:`SessionProtocol`."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits: int = 0
        self.queries: list[tuple[type[object], object]] = []
        self.results: dict[object, object] = {}

    def get(self, entity: type[object], ident: object, /, **kwargs: object) -> object | None:
        self.queries.append((entity, ident))
        return self.results.get(ident)

    def add(self, instance: object, /, **kwargs: object) -> None:
        self.added.append(instance)

    def commit(self) -> None:
        self.commits += 1


class _CommandServiceImpl:
    def __init__(self) -> None:
        self.ingested: list[Document] = []
        self.retired: list[DocumentId] = []

    def ingest_document(self, document: Document) -> DocumentId:
        self.ingested.append(document)
        return document.id

    def retire_document(self, document_id: DocumentId) -> None:
        self.retired.append(document_id)


class _QueryServiceImpl:
    def __init__(self, *, document: Document | None = None) -> None:
        self.document = document
        self.requests: list[tuple[str, object]] = []

    def get_document(self, document_id: DocumentId) -> Document | None:
        self.requests.append(("get", document_id))
        return self.document

    def list_documents(self, *, limit: int = 20) -> list[Document]:
        self.requests.append(("list", limit))
        return [self.document] if self.document else []


@pytest.mark.parametrize("proto, impl", [
    (CommandService, _CommandServiceImpl()),
    (QueryService, _QueryServiceImpl()),
])
def test_runtime_protocol_implementations(proto: type[object], impl: object) -> None:
    """Ensure runtime-checkable protocols accept structural implementations."""

    assert isinstance(impl, proto)


def test_session_protocol_contract() -> None:
    """Validate behaviour expected by :class:`SessionProtocol`."""

    session = _FakeSession()
    payload = object()

    session.add(payload)
    session.commit()

    assert session.added == [payload]
    assert session.commits == 1

    document_id = DocumentId("doc-1")
    session.results[document_id] = Document(
        id=document_id,
        metadata=DocumentMetadata(title="Test", source="Unit"),
        scripture_refs=("John.3.16",),
    )
    retrieved = session.get(Document, document_id)

    assert isinstance(retrieved, Document)
    assert session.queries == [(Document, document_id)]


def test_session_protocol_missing_method_raises() -> None:
    """Objects lacking required methods should fail when used via the protocol."""

    class _IncompleteSession:
        def get(self, entity: type[object], ident: object, /, **kwargs: object) -> object | None:  # pragma: no cover - exercised via AttributeError
            return None

    def use_session(session: SessionProtocol) -> None:
        session.add(object())

    with pytest.raises(AttributeError):
        use_session(_IncompleteSession())
