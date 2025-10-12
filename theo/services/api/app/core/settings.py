"""Legacy shim forwarding to :mod:`theo.application.facades.settings`."""
from __future__ import annotations

from warnings import warn

from theo.application.facades.settings import *  # noqa: F401,F403

warn(
    "Importing from 'theo.services.api.app.core.settings' is deprecated; "
    "use 'theo.application.facades.settings' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "Settings",
    "get_settings",
    "get_settings_cipher",
]
