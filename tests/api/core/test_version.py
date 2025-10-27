"""Tests for the legacy version shim module."""
from __future__ import annotations

from theo.application.facades import version as facades_version

from tests.api.core import import_legacy_module


MODULE_NAME = "theo.infrastructure.api.app.core.version"
EXPECTED_EXPORTS = ["get_git_sha"]


def test_version_shim_warns_and_reexports_get_git_sha():
    """Importing the shim should warn and expose the facade helper."""
    module, warning = import_legacy_module(MODULE_NAME)

    assert "deprecated" in str(warning.message)
    assert module.get_git_sha is facades_version.get_git_sha
    assert module.__all__ == EXPECTED_EXPORTS
