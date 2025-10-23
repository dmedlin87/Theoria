"""Facade for resolving the configured graph projector."""
from __future__ import annotations

import logging
from functools import lru_cache

from theo.application.graph import GraphProjector, NullGraphProjector

from .settings import get_settings

try:  # pragma: no cover - optional dependency resolution
    from theo.adapters.graph.neo4j import Neo4jGraphProjector
except Exception:  # pragma: no cover - fallback when neo4j unavailable
    Neo4jGraphProjector = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_graph_projector() -> GraphProjector:
    """Return the configured graph projector or a no-op implementation."""

    settings = get_settings()
    if not getattr(settings, "graph_projection_enabled", False):
        return NullGraphProjector()

    uri = getattr(settings, "graph_neo4j_uri", None)
    if not uri:
        logger.warning("Graph projection enabled but graph_neo4j_uri is not set")
        return NullGraphProjector()

    if Neo4jGraphProjector is None:  # pragma: no cover - dependency guard
        logger.warning("Neo4j driver not available; graph projection disabled")
        return NullGraphProjector()

    username = getattr(settings, "graph_neo4j_username", None)
    password = getattr(settings, "graph_neo4j_password", None)
    database = getattr(settings, "graph_neo4j_database", None)

    try:
        projector = Neo4jGraphProjector.from_config(
            uri,
            user=username,
            password=password,
            database=database,
        )
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("Failed to initialise Neo4j graph projector")
        return NullGraphProjector()
    return projector


__all__ = ["get_graph_projector"]
