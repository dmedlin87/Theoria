"""Compatibility layer for :mod:`theo.application.facades.settings_store`.

The services API exposed the settings persistence helpers via this
module.  We now source them from the facades package but re-export the
original names here so older imports survive while alerting callers that
they should migrate.
"""

from __future__ import annotations

import warnings

from theo.application.facades import settings_store as _facade

warnings.warn(
    "Importing 'theo.infrastructure.api.app.core.settings_store' is deprecated. "
    "Use 'theo.application.facades.settings_store' instead.",
    DeprecationWarning,
    stacklevel=2,
)

SETTINGS_NAMESPACE = _facade.SETTINGS_NAMESPACE
SettingNotFoundError = _facade.SettingNotFoundError
load_setting = _facade.load_setting
require_setting = _facade.require_setting
save_setting = _facade.save_setting

__all__ = [
    "SETTINGS_NAMESPACE",
    "SettingNotFoundError",
    "load_setting",
    "require_setting",
    "save_setting",
]
