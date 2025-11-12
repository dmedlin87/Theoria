"""Legacy compatibility layer for :mod:`theo.application.facades.database`.

The services API historically exposed database helpers from the legacy core
namespace.  The code base now routes all callers through
:mod:`theo.application.facades.database`; this module re-exports those helpers
while emitting a deprecation warning on first import so existing integrations
keep working.
"""

from __future__ import annotations

import warnings

from theo.application.facades import database as _facade

warnings.warn(
    f"Importing '{__name__}' is deprecated. "
    "Use 'theo.application.facades.database' instead.",
    DeprecationWarning,
    stacklevel=2,
)

Base = _facade.Base
configure_engine = _facade.configure_engine
get_engine = _facade.get_engine
get_session = _facade.get_session

__all__ = ["Base", "configure_engine", "get_engine", "get_session"]
