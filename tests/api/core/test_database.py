"""Tests for the legacy database shim module."""
from __future__ import annotations

from theo.application.facades import database as facades_database

from tests.api.core import import_legacy_module


MODULE_NAME = "theo.services.api.app.core.database"
EXPECTED_EXPORTS = ["Base", "configure_engine", "get_engine", "get_session"]


def test_database_shim_emits_deprecation_warning_and_reexports_facade_symbols():
    """Importing the shim should warn and expose the facade objects verbatim."""
    module, warning = import_legacy_module(MODULE_NAME)

    assert "deprecated" in str(warning.message)
    assert module.Base is facades_database.Base
    assert module.configure_engine is facades_database.configure_engine
    assert module.get_engine is facades_database.get_engine
    assert module.get_session is facades_database.get_session
    assert module.__all__ == EXPECTED_EXPORTS
