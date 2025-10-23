import pytest
from types import SimpleNamespace

from theo.domain import Document, DocumentId, DocumentMetadata
from theo.platform import application as application_module


class DummyResearchService:
    def __init__(self, notes_repository, hypothesis_repository, fetch_dss_links_func):
        self.notes_repository = notes_repository
        self.hypothesis_repository = hypothesis_repository
        self.fetch_dss_links_func = fetch_dss_links_func


class DummyRepositoryFactory:
    def __init__(self, label):
        self.label = label
        self.calls = []

    def __call__(self, session):
        self.calls.append(session)
        return f"{self.label}:{id(session)}"


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch):
    # Ensure resolve_application cache is cleared between tests
    application_module.resolve_application.cache_clear()
    yield
    application_module.resolve_application.cache_clear()


def test_resolve_application_wires_container(monkeypatch):
    fake_registry_calls = {}

    def fake_ingest(registry, document):
        fake_registry_calls.setdefault("ingest", []).append((registry, document))
        return document.id

    def fake_retire(registry, document_id):
        fake_registry_calls.setdefault("retire", []).append((registry, document_id))

    def fake_get(registry, document_id):
        fake_registry_calls.setdefault("get", []).append((registry, document_id))
        return f"retrieved:{document_id}"

    def fake_list(registry, limit=20):
        fake_registry_calls.setdefault("list", []).append((registry, limit))
        return [f"doc-{limit}"]

    notes_factory = DummyRepositoryFactory("notes")
    hypotheses_factory = DummyRepositoryFactory("hypotheses")

    monkeypatch.setattr(application_module, "_ingest_document", fake_ingest)
    monkeypatch.setattr(application_module, "_retire_document", fake_retire)
    monkeypatch.setattr(application_module, "_get_document", fake_get)
    monkeypatch.setattr(application_module, "_list_documents", fake_list)
    monkeypatch.setattr(
        application_module,
        "SqlAlchemyResearchNoteRepositoryFactory",
        lambda: notes_factory,
    )
    monkeypatch.setattr(
        application_module,
        "SqlAlchemyHypothesisRepositoryFactory",
        lambda: hypotheses_factory,
    )
    monkeypatch.setattr(application_module, "ResearchService", DummyResearchService)

    fetch_marker = object()
    monkeypatch.setattr(
        "theo.domain.research.fetch_dss_links", lambda: fetch_marker
    )

    container, registry = application_module.resolve_application()

    metadata = DocumentMetadata(title="Test", source="tests")
    document = Document(DocumentId("doc-1"), metadata=metadata, scripture_refs=())

    result_id = container.ingest_document(document)
    assert result_id == document.id
    assert fake_registry_calls["ingest"][0][1] == document

    fetched = container.get_document(document.id)
    assert fetched == f"retrieved:{document.id}"

    listed = container.list_documents(limit=5)
    assert listed == ["doc-5"]

    container.retire_document(document.id)
    assert fake_registry_calls["retire"][0][1] == document.id

    session = object()
    research_service = container.research_service_factory(session)
    assert isinstance(research_service, DummyResearchService)
    assert notes_factory.calls == [session]
    assert hypotheses_factory.calls == [session]
    assert callable(research_service.fetch_dss_links_func)
    assert research_service.fetch_dss_links_func() is fetch_marker

    # Registry should expose registered factories
    assert "settings" in registry.factories
    assert "engine" in registry.factories


def test_extract_language_prefers_explicit_language_key():
    record = SimpleNamespace(bib_json={"language": "grc", "lang": "en"})

    assert application_module._extract_language(record) == "grc"


def test_extract_language_returns_none_when_missing_or_blank():
    record = SimpleNamespace(bib_json={"language": "   ", "lang": None})

    assert application_module._extract_language(record) is None


def test_extract_tags_combines_topics_and_payload_tags():
    record = SimpleNamespace(
        topics=["apologetics", "history", "apologetics", "", None],
        bib_json={"tags": ("history", "exegesis", "apologetics", "")},
    )

    assert application_module._extract_tags(record) == [
        "apologetics",
        "history",
        "exegesis",
    ]


def test_extract_tags_handles_dictionary_topics_and_ignores_invalid_entries():
    record = SimpleNamespace(
        topics={"primary": "patristics", "secondary": 42},
        bib_json="not-a-dict",
    )

    assert application_module._extract_tags(record) == ["patristics"]


class _RecordingSession:
    def __init__(self, rows: list[tuple[str, ...]]):
        self._rows = rows
        self.executed = []

    def execute(self, statement):
        self.executed.append(statement)
        return self._rows


def test_extract_scripture_refs_merges_payload_and_database_results():
    session = _RecordingSession(rows=[("John.1.1",), ("Gen.1.1",), ("Rev.22.13",)])
    record = SimpleNamespace(
        bib_json={"scripture_refs": ["Gen.1.1", "Exod.3.14", "", None, "Gen.1.1"]},
        id="doc-1",
    )

    result = application_module._extract_scripture_refs(session, record)

    assert result == ("Gen.1.1", "Exod.3.14", "John.1.1", "Rev.22.13")
    assert len(session.executed) == 1
