"""Compatibility shim forwarding to :mod:`theo.application.facades.research`."""
from __future__ import annotations

from warnings import warn

from ..compat.research.notes import *  # noqa: F401,F403

warn(
    "Importing from 'theo.services.api.app.research.notes' is deprecated; "
    "use 'theo.application.facades.research' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "ResearchNote",
    "ResearchNoteNotFoundError",
    "create_research_note",
    "generate_research_note_preview",
    "get_notes_for_osis",
    "update_research_note",
    "delete_research_note",
]
