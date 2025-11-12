"""Smoke tests for application facade imports used by API services."""
from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any

import pytest


FACADE_DEFINITIONS = [
    {
        "module": "theo.application.facades.database",
        "exports": ["Base", "configure_engine", "get_engine", "get_session"],
    },
    {
        "module": "theo.application.facades.runtime",
        "exports": ["allow_insecure_startup", "current_runtime_environment"],
    },
    {
        "module": "theo.application.facades.secret_migration",
        "exports": ["migrate_secret_settings"],
    },
    {
        "module": "theo.application.facades.settings",
        "exports": ["Settings", "get_settings", "get_settings_cipher"],
    },
    {
        "module": "theo.application.facades.settings_store",
        "exports": [
            "SETTINGS_NAMESPACE",
            "SettingNotFoundError",
            "load_setting",
            "require_setting",
            "save_setting",
        ],
    },
    {
        "module": "theo.application.facades.version",
        "exports": ["get_git_sha"],
    },
]


def _import_module(name: str) -> ModuleType:
    sys.modules.pop(name, None)
    return importlib.import_module(name)


@pytest.mark.parametrize("definition", FACADE_DEFINITIONS)
def test_facades_expose_expected_exports(definition: dict[str, Any]) -> None:
    module = _import_module(definition["module"])
    for export in definition["exports"]:
        assert hasattr(module, export)
    declared = getattr(module, "__all__", definition["exports"])
    for export in definition["exports"]:
        assert export in declared
