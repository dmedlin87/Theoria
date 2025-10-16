import pytest

from theo.adapters import AdapterRegistry
from theo.application import ApplicationContainer
from theo.domain import Document, DocumentId, DocumentMetadata
from theo.services.bootstrap import resolve_application


@pytest.fixture(autouse=True)
def clear_resolve_application_cache():
    resolve_application.cache_clear()
    yield
    resolve_application.cache_clear()


@pytest.fixture
def sample_document() -> Document:
    return Document(
        id=DocumentId("doc-1"),
        metadata=DocumentMetadata(title="Doc", source="tests"),
        scripture_refs=("John.3.16",),
    )


def test_resolve_application_returns_container_and_registry(sample_document):
    container, registry = resolve_application()

    assert isinstance(container, ApplicationContainer)
    assert isinstance(registry, AdapterRegistry)

    expected_ports = {
        "settings",
        "engine",
        "research_notes_repository_factory",
        "hypotheses_repository_factory",
        "research_service_factory",
    }
    assert expected_ports.issubset(registry.factories.keys())

    assert container.bind_command()(sample_document) is None
    container.bind_retire()(sample_document.id)
    assert container.bind_get()(sample_document.id) is None
    assert container.bind_list()() == []


def test_resolve_application_results_are_cached(sample_document):
    first_container, first_registry = resolve_application()
    second_container, second_registry = resolve_application()

    assert first_container is second_container
    assert first_registry is second_registry
