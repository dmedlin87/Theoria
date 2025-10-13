"""Compatibility shim forwarding to :mod:`theo.domain.research.dss_links`."""
from __future__ import annotations

from warnings import warn

from ..compat.research.dss_links import *  # noqa: F401,F403

warn(
    "Importing from 'theo.services.api.app.research.dss_links' is deprecated; "
    "use 'theo.domain.research.dss_links' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["DssLinkEntry", "fetch_dss_links", "dss_links_dataset"]
