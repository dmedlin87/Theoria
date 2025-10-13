"""Compatibility shim forwarding to :mod:`theo.domain.research.crossrefs`."""
from __future__ import annotations

from warnings import warn

from ..compat.research.crossrefs import (
    CrossReferenceEntry,
    fetch_cross_references,
)

warn(
    "Importing from 'theo.services.api.app.research.crossrefs' is deprecated; "
    "use 'theo.domain.research.crossrefs' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["CrossReferenceEntry", "fetch_cross_references"]
