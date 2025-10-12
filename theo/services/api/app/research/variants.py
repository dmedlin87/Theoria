"""Compatibility shim forwarding to :mod:`theo.domain.research.variants`."""
from __future__ import annotations

from warnings import warn

from ..compat.research.variants import *  # noqa: F401,F403

warn(
    "Importing from 'theo.services.api.app.research.variants' is deprecated; "
    "use 'theo.domain.research.variants' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["VariantEntry", "variants_apparatus"]
