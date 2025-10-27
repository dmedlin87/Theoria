"""Tests for the legacy settings store shim module."""
from __future__ import annotations

from theo.application.facades import settings_store as facades_settings_store

from tests.api.core import import_legacy_module


MODULE_NAME = "theo.infrastructure.api.app.core.settings_store"
EXPECTED_EXPORTS = [
    "SETTINGS_NAMESPACE",
    "SettingNotFoundError",
    "load_setting",
    "require_setting",
    "save_setting",
]


def test_settings_store_shim_warns_and_reexports_store_facade():
    """Importing the shim should warn and expose the facade store helpers."""
    module, warning = import_legacy_module(MODULE_NAME)

    assert "deprecated" in str(warning.message)
    assert module.SETTINGS_NAMESPACE is facades_settings_store.SETTINGS_NAMESPACE
    assert module.SettingNotFoundError is facades_settings_store.SettingNotFoundError
    assert module.load_setting is facades_settings_store.load_setting
    assert module.require_setting is facades_settings_store.require_setting
    assert module.save_setting is facades_settings_store.save_setting
    assert module.__all__ == EXPECTED_EXPORTS
