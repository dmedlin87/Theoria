"""Service-layer bootstrap helpers bridging to the application container."""
from __future__ import annotations

from functools import lru_cache
from typing import Callable, Tuple

from theo.adapters import AdapterRegistry
from theo.application.embeddings import EmbeddingRebuildService
from theo.application.facades.database import get_engine
from theo.application.facades.documents import build_document_facade
from theo.application.facades.embeddings import build_embedding_rebuild_service
from theo.application.facades.research_persistence import (
    get_hypothesis_repository_factory,
    get_research_note_repository_factory,
)
from theo.application.facades.settings import get_settings
from theo.application.interfaces import SessionProtocol
from theo.application.research import ResearchService
from theo.domain.research import fetch_dss_links

from .container import ApplicationContainer


@lru_cache(maxsize=1)
def resolve_application() -> Tuple[ApplicationContainer, AdapterRegistry]:
    """Initialise the application container and adapter registry."""

    registry = AdapterRegistry()
    registry.register("settings", get_settings)
    registry.register("engine", get_engine)
    registry.register(
        "research_notes_repository_factory",
        get_research_note_repository_factory,
    )
    registry.register(
        "hypotheses_repository_factory",
        get_hypothesis_repository_factory,
    )

    document_facade = build_document_facade(registry)

    def _build_research_service_factory() -> Callable[[SessionProtocol], ResearchService]:
        notes_factory = registry.resolve("research_notes_repository_factory")
        hypotheses_factory = registry.resolve("hypotheses_repository_factory")

        def _factory(session: SessionProtocol) -> ResearchService:
            notes_repository = notes_factory(session)
            hypotheses_repository = hypotheses_factory(session)
            return ResearchService(
                notes_repository,
                hypothesis_repository=hypotheses_repository,
                fetch_dss_links_func=fetch_dss_links,
            )

        return _factory

    registry.register("research_service_factory", _build_research_service_factory)

    embedding_rebuild_service: EmbeddingRebuildService = build_embedding_rebuild_service(
        registry
    )
    registry.register(
        "embedding_rebuild_service", lambda: embedding_rebuild_service
    )

    container = ApplicationContainer(
        ingest_document=document_facade.ingest,
        retire_document=document_facade.retire,
        get_document=document_facade.get,
        list_documents=document_facade.list,
        research_service_factory=_build_research_service_factory(),
    )
    return container, registry


__all__ = ["resolve_application"]
