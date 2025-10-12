"""Compatibility shim forwarding to :mod:`theo.application.research`."""
from __future__ import annotations

from warnings import warn

from ..compat.research.reports import *  # noqa: F401,F403

warn(
    "Importing from 'theo.services.api.app.research.reports' is deprecated; "
    "use 'theo.application.research' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["ReportSection", "ResearchReport", "report_build"]
