"""Legacy shim forwarding to :mod:`theo.application.facades.settings_store`."""
from __future__ import annotations

from warnings import warn

from theo.application.facades.settings_store import *  # noqa: F401,F403

warn(
    "Importing from 'theo.services.api.app.core.settings_store' is deprecated; "
    "use 'theo.application.facades.settings_store' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "SETTINGS_NAMESPACE",
    "SettingNotFoundError",
    "load_setting",
    "require_setting",
    "save_setting",
]
