"""Facade helpers exposing research application services."""
from __future__ import annotations

from theo.application.research import ResearchService
from theo.application.interfaces import SessionProtocol
from theo.domain.research import (
    HypothesisDraft,
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
)
from theo.services.bootstrap import resolve_application

__all__ = [
    "ResearchService",
    "ResearchNoteDraft",
    "ResearchNoteEvidenceDraft",
    "HypothesisDraft",
    "get_research_service",
]


def get_research_service(session: SessionProtocol) -> ResearchService:
    """Return a research service bound to the provided session."""

    container, _registry = resolve_application()
    return container.get_research_service(session)
