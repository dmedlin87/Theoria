"""Tests for the legacy secret migration shim module."""
from __future__ import annotations

from theo.application.facades import secret_migration as facades_secret_migration

from tests.api.core import import_legacy_module


MODULE_NAME = "theo.services.api.app.core.secret_migration"
EXPECTED_EXPORTS = ["migrate_secret_settings"]


def test_secret_migration_shim_warns_and_reexports_migration_helper():
    """Importing the shim should warn and expose the facade migration helper."""
    module, warning = import_legacy_module(MODULE_NAME)

    assert "deprecated" in str(warning.message)
    assert module.migrate_secret_settings is facades_secret_migration.migrate_secret_settings
    assert module.__all__ == EXPECTED_EXPORTS
