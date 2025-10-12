"""Compatibility re-export for morphology helpers."""
from __future__ import annotations

from warnings import warn

from theo.domain.research.morphology import MorphToken, fetch_morphology

warn(
    "Importing from 'theo.services.api.app.research.morphology' is deprecated; "
    "use 'theo.domain.research.morphology' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["MorphToken", "fetch_morphology"]
