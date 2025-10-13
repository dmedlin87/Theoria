"""Legacy shim forwarding to :mod:`theo.application.facades.database`."""
from __future__ import annotations

from warnings import warn

from theo.application.facades.database import (
    Base,
    configure_engine,
    get_engine,
    get_session,
)

warn(
    "Importing from 'theo.services.api.app.core.database' is deprecated; "
    "use 'theo.application.facades.database' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "Base",
    "configure_engine",
    "get_engine",
    "get_session",
]
