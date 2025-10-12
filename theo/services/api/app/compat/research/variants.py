"""Compatibility re-export for textual variant helpers."""
from __future__ import annotations

from warnings import warn

from theo.domain.research.variants import VariantEntry, variants_apparatus

warn(
    "Importing from 'theo.services.api.app.research.variants' is deprecated; "
    "use 'theo.domain.research.variants' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["VariantEntry", "variants_apparatus"]
