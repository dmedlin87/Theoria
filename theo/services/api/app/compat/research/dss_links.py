"""Compatibility re-export for Dead Sea Scroll linkage helpers."""
from __future__ import annotations

from warnings import warn

from theo.domain.research.dss_links import DssLinkEntry, fetch_dss_links

warn(
    "Importing from 'theo.services.api.app.research.dss_links' is deprecated; "
    "use 'theo.domain.research.dss_links' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["DssLinkEntry", "fetch_dss_links"]
