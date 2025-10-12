"""Compatibility shim forwarding to :mod:`theo.domain.research.fallacies`."""
from __future__ import annotations

from warnings import warn

from ..compat.research.fallacies import *  # noqa: F401,F403

warn(
    "Importing from 'theo.services.api.app.research.fallacies' is deprecated; "
    "use 'theo.domain.research.fallacies' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["FallacyHit", "fallacy_detect"]
