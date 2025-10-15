"""Tests for the legacy runtime shim module."""
from __future__ import annotations

from theo.application.facades import runtime as facades_runtime

from tests.api.core import import_legacy_module


MODULE_NAME = "theo.services.api.app.core.runtime"
EXPECTED_EXPORTS = ["allow_insecure_startup"]


def test_runtime_shim_warns_and_reexports_allow_insecure_startup():
    """Importing the runtime shim should warn and expose the facade helper."""
    module, warning = import_legacy_module(MODULE_NAME)

    assert "deprecated" in str(warning.message)
    assert module.allow_insecure_startup is facades_runtime.allow_insecure_startup
    assert module.__all__ == EXPECTED_EXPORTS
