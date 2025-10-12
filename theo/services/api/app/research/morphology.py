"""Compatibility shim forwarding to :mod:`theo.domain.research.morphology`."""
from __future__ import annotations

from warnings import warn

from ..compat.research.morphology import *  # noqa: F401,F403

warn(
    "Importing from 'theo.services.api.app.research.morphology' is deprecated; "
    "use 'theo.domain.research.morphology' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["MorphToken", "fetch_morphology"]
