"""Compatibility shim forwarding to :mod:`theo.domain.research.scripture`."""
from __future__ import annotations

from warnings import warn

from ..compat.research.scripture import *  # noqa: F401,F403

warn(
    "Importing from 'theo.services.api.app.research.scripture' is deprecated; "
    "use 'theo.domain.research.scripture' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Verse", "fetch_passage"]
