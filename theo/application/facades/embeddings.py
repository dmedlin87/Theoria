"""Facade bridging embedding rebuild dependencies."""
from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy.orm import Session

from theo.adapters import AdapterRegistry
from theo.application.embeddings import EmbeddingRebuildService
from theo.application.interfaces import SessionProtocol

__all__ = ["build_embedding_rebuild_service"]


class _RepositoryFactory(Protocol):
    def __call__(self, session: SessionProtocol) -> Any: ...


def _resolve_embedding_modules() -> tuple[
    Callable[[], Any],
    Callable[[], None],
    Callable[[str], str],
    _RepositoryFactory,
]:
    embeddings_module = importlib.import_module(
        "theo.infrastructure.api.app.ingest.embeddings"
    )
    sanitizer_module = importlib.import_module(
        "theo.infrastructure.api.app.ingest.sanitizer"
    )
    repository_module = importlib.import_module(
        "theo.adapters.persistence.embedding_repository"
    )
    get_embedding_service = getattr(embeddings_module, "get_embedding_service")
    clear_embedding_cache = getattr(embeddings_module, "clear_embedding_cache")
    sanitize_passage_text = getattr(sanitizer_module, "sanitize_passage_text")
    repository_factory = getattr(
        repository_module, "SQLAlchemyPassageEmbeddingRepository"
    )
    return (
        get_embedding_service,
        clear_embedding_cache,
        sanitize_passage_text,
        repository_factory,
    )


def _session_factory(registry: AdapterRegistry) -> Callable[[], SessionProtocol]:
    def _factory() -> SessionProtocol:
        engine = registry.resolve("engine")
        return Session(engine)

    return _factory



def build_embedding_rebuild_service(
    registry: AdapterRegistry,
) -> EmbeddingRebuildService:
    """Construct an :class:`EmbeddingRebuildService` wired to infrastructure."""

    (
        get_embedding_service,
        clear_embedding_cache,
        sanitize_passage_text,
        repository_cls,
    ) = _resolve_embedding_modules()

    session_factory = _session_factory(registry)

    def _factory(session: SessionProtocol):
        return repository_cls(session)  # type: ignore[call-arg]

    return EmbeddingRebuildService(
        session_factory=session_factory,
        repository_factory=_factory,
        embedding_service=get_embedding_service(),
        sanitize_text=sanitize_passage_text,
        cache_clearer=clear_embedding_cache,
    )
