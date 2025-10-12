"""Compatibility re-export for fallacy detection helpers."""
from __future__ import annotations

from warnings import warn

from theo.domain.research.fallacies import FallacyHit, fallacy_detect

warn(
    "Importing from 'theo.services.api.app.research.fallacies' is deprecated; "
    "use 'theo.domain.research.fallacies' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["FallacyHit", "fallacy_detect"]
