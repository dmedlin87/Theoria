"""Legacy shim for :mod:`theo.application.facades.settings`.

The application previously initialised configuration via a legacy core
namespace.  To avoid breaking downstream integrations we mirror the facade
symbols here and warn once when the module is imported.
"""

from __future__ import annotations

import warnings

from theo.application.facades import settings as _facade

warnings.warn(
    f"Importing '{__name__}' is deprecated. "
    "Use 'theo.application.facades.settings' instead.",
    DeprecationWarning,
    stacklevel=2,
)

Settings = _facade.Settings
get_settings = _facade.get_settings
get_settings_cipher = _facade.get_settings_cipher

__all__ = ["Settings", "get_settings", "get_settings_cipher"]
