"""Compatibility shim forwarding to :mod:`theo.application.facades.research`."""
from __future__ import annotations

from warnings import warn

from ..compat.research.overview import (
    OverviewBullet,
    ReliabilityOverview,
    build_reliability_overview,
)

warn(
    "Importing from 'theo.services.api.app.research.overview' is deprecated; "
    "use 'theo.application.facades.research' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["OverviewBullet", "ReliabilityOverview", "build_reliability_overview"]
