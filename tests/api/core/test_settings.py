"""Tests for the legacy settings shim module."""
from __future__ import annotations

from theo.application.facades import settings as facades_settings

from tests.api.core import import_legacy_module


MODULE_NAME = "theo.services.api.app.core.settings"
EXPECTED_EXPORTS = ["Settings", "get_settings", "get_settings_cipher"]


def test_settings_shim_warns_and_reexports_settings_facade():
    """Importing the shim should warn and expose the facade settings helpers."""
    module, warning = import_legacy_module(MODULE_NAME)

    assert "deprecated" in str(warning.message)
    assert module.Settings is facades_settings.Settings
    assert module.get_settings is facades_settings.get_settings
    assert module.get_settings_cipher is facades_settings.get_settings_cipher
    assert module.__all__ == EXPECTED_EXPORTS
