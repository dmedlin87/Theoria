"""Service-layer bootstrap helpers bridging to the application container."""
from __future__ import annotations

from functools import lru_cache
from typing import Callable, Tuple

from sqlalchemy.orm import Session

from theo.adapters import AdapterRegistry
from theo.adapters.research import (
    SqlAlchemyHypothesisRepositoryFactory,
    SqlAlchemyResearchNoteRepositoryFactory,
)
from theo.application import ApplicationContainer
from theo.application.facades.database import get_engine
from theo.application.facades.settings import get_settings
from theo.application.research import ResearchService
from theo.application.reasoner import NeighborhoodReasoner
from theo.platform import bootstrap_application


def _noop_command(*_args, **_kwargs):  # pragma: no cover - transitional shim
    return None


def _noop_retire(*_args, **_kwargs) -> None:  # pragma: no cover - transitional shim
    return None


def _noop_get(*_args, **_kwargs):  # pragma: no cover - transitional shim
    return None


def _noop_list(*_args, **_kwargs):  # pragma: no cover - transitional shim
    return []


@lru_cache(maxsize=1)
def resolve_application() -> Tuple[ApplicationContainer, AdapterRegistry]:
    """Initialise the application container and adapter registry."""

    registry = AdapterRegistry()
    registry.register("settings", get_settings)
    registry.register("engine", get_engine)
    registry.register(
        "research_notes_repository_factory",
        lambda: SqlAlchemyResearchNoteRepositoryFactory(),
    )
    registry.register(
        "hypotheses_repository_factory",
        lambda: SqlAlchemyHypothesisRepositoryFactory(),
    )

    def _build_research_service_factory() -> Callable[[Session], ResearchService]:
        from theo.domain.research import fetch_dss_links

        notes_factory = registry.resolve("research_notes_repository_factory")
        hypotheses_factory = registry.resolve("hypotheses_repository_factory")

        def _factory(session: Session) -> ResearchService:
            notes_repository = notes_factory(session)
            hypotheses_repository = hypotheses_factory(session)
            return ResearchService(
                notes_repository,
                hypothesis_repository=hypotheses_repository,
                fetch_dss_links_func=fetch_dss_links,
            )

        return _factory

    registry.register("research_service_factory", _build_research_service_factory)

    def _build_reasoner_factory() -> Callable[[], NeighborhoodReasoner]:
        def _factory() -> NeighborhoodReasoner:
            return NeighborhoodReasoner()

        return _factory

    registry.register("reasoner_factory", _build_reasoner_factory)

    container = bootstrap_application(
        registry=registry,
        command_factory=lambda: _noop_command,
        retire_factory=lambda: _noop_retire,
        get_factory=lambda: _noop_get,
        list_factory=lambda: _noop_list,
        research_factory=lambda: registry.resolve("research_service_factory"),
    )
    return container, registry
