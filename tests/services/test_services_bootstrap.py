from __future__ import annotations

import pytest

from theo.adapters import AdapterRegistry
from theo.application import ApplicationContainer
from theo.application.facades.database import Base, configure_engine, get_engine
from theo.domain import Document, DocumentId, DocumentMetadata
from theo.platform.application import resolve_application as platform_resolve_application
from theo.services.bootstrap import resolve_application


@pytest.fixture
def sample_document() -> Document:
    return Document(
        id=DocumentId("doc-1"),
        metadata=DocumentMetadata(title="Doc", source="tests"),
        scripture_refs=("John.3.16",),
    )


@pytest.fixture
def database(tmp_path):
    db_path = tmp_path / "application.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_resolve_application_returns_container_and_registry(
    sample_document,
    database,
    application_container_factory,
):
    with application_container_factory():
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

        command = container.bind_command()
        retire = container.bind_retire()
        getter = container.bind_get()
        lister = container.bind_list()

        assert lister() == []

        ingested_id = command(sample_document)
        assert ingested_id == sample_document.id

        stored = getter(sample_document.id)
        assert stored is not None
        assert stored.metadata.title == sample_document.metadata.title
        assert stored.metadata.source == sample_document.metadata.source
        assert stored.scripture_refs == sample_document.scripture_refs

        listed = lister(limit=5)
        assert any(document.id == sample_document.id for document in listed)

        retire(sample_document.id)
        assert getter(sample_document.id) is None


def test_resolve_application_results_are_cached(
    sample_document,
    database,
    application_container_factory,
):
    with application_container_factory():
        first_container, first_registry = resolve_application()
        second_container, second_registry = resolve_application()

        assert first_container is second_container
        assert first_registry is second_registry


def test_service_wrapper_exposes_platform_bootstrap():
    assert resolve_application is platform_resolve_application

