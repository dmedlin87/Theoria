"""Repository contract for research notes."""
from __future__ import annotations

from typing import Mapping, Protocol, Sequence

from ..research import (
    ResearchNote,
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
)


class ResearchNoteRepository(Protocol):
    """Persistence operations for research notes."""

    def create(
        self,
        draft: ResearchNoteDraft,
        *,
        commit: bool = True,
    ) -> ResearchNote:
        """Persist a research note and return the stored aggregate."""

    def preview(self, draft: ResearchNoteDraft) -> ResearchNote:
        """Render a research note preview without committing it to the database."""

    def list_for_osis(
        self,
        osis: str,
        *,
        stance: str | None = None,
        claim_type: str | None = None,
        tag: str | None = None,
        min_confidence: float | None = None,
    ) -> list[ResearchNote]:
        """Return notes linked to an OSIS reference."""

    def update(
        self,
        note_id: str,
        changes: Mapping[str, object],
        *,
        evidences: Sequence[ResearchNoteEvidenceDraft] | None = None,
    ) -> ResearchNote:
        """Apply updates to a persisted note and return the refreshed aggregate."""

    def delete(self, note_id: str) -> None:
        """Remove a research note and cascade delete any attached evidence."""


__all__ = ["ResearchNoteRepository"]
