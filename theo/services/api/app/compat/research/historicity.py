"""Compatibility re-export for historicity helpers."""
from __future__ import annotations

from warnings import warn

from theo.domain.research.historicity import HistoricityEntry, historicity_search

warn(
    "Importing from 'theo.services.api.app.research.historicity' is deprecated; "
    "use 'theo.domain.research.historicity' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["HistoricityEntry", "historicity_search"]
