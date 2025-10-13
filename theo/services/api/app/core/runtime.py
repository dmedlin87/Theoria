"""Legacy shim forwarding to :mod:`theo.application.facades.runtime`."""
from __future__ import annotations

from warnings import warn

from theo.application.facades.runtime import allow_insecure_startup

warn(
    "Importing from 'theo.services.api.app.core.runtime' is deprecated; "
    "use 'theo.application.facades.runtime' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["allow_insecure_startup"]
