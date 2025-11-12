"""Facade exposing research repository factories."""
from __future__ import annotations

from theo.adapters.research import (
    SqlAlchemyHypothesisRepositoryFactory,
    SqlAlchemyResearchNoteRepositoryFactory,
)

__all__ = [
    "get_hypothesis_repository_factory",
    "get_research_note_repository_factory",
]


def get_research_note_repository_factory() -> SqlAlchemyResearchNoteRepositoryFactory:
    """Return the configured research note repository factory."""

    return SqlAlchemyResearchNoteRepositoryFactory()


def get_hypothesis_repository_factory() -> SqlAlchemyHypothesisRepositoryFactory:
    """Return the configured hypothesis repository factory."""

    return SqlAlchemyHypothesisRepositoryFactory()
