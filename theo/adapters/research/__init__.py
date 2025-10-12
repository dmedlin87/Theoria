"""Research adapters."""
from .sqlalchemy import (
    SqlAlchemyResearchNoteRepository,
    SqlAlchemyResearchNoteRepositoryFactory,
)

__all__ = [
    "SqlAlchemyResearchNoteRepository",
    "SqlAlchemyResearchNoteRepositoryFactory",
]
