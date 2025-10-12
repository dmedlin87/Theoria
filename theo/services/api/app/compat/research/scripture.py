"""Compatibility re-export for scripture helpers."""
from __future__ import annotations

from warnings import warn

from theo.domain.research.scripture import Verse, fetch_passage

warn(
    "Importing from 'theo.services.api.app.research.scripture' is deprecated; "
    "use 'theo.domain.research.scripture' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Verse", "fetch_passage"]
