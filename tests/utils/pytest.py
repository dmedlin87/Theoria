"""Shared pytest helpers for the Theoria test-suite."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FIXTURE_MARKER_REQUIREMENTS: dict[str, set[str]] = {
    "pgvector": {
        "pgvector_container",
        "pgvector_database_url",
        "pgvector_engine",
        "pgvector_migrated_database_url",
    },
    "schema": {
        "integration_database_url",
        "integration_engine",
    },
}

MARKER_OPTIONS: dict[str, str] = {
    "pgvector": "pgvector",
    "schema": "schema",
    "contract": "contract",
    "gpu": "gpu",
}


def ensure_project_root_on_path() -> None:
    import sys

    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def register_randomly_plugin(pluginmanager: pytest.PluginManager) -> bool:
    """Ensure pytest-randomly is registered when available."""

    if pluginmanager.hasplugin("randomly"):
        return True

    try:
        plugin_module = importlib.import_module("pytest_randomly.plugin")
    except ModuleNotFoundError:
        return False

    pluginmanager.register(plugin_module, "pytest_randomly")
    return True


def register_xdist_plugin(pluginmanager: pytest.PluginManager) -> bool:
    """Ensure pytest-xdist is eagerly registered when the dependency exists."""

    if pluginmanager.hasplugin("xdist"):
        return True

    try:
        plugin_module = importlib.import_module("xdist.plugin")
    except ModuleNotFoundError:
        return False

    pluginmanager.register(plugin_module, "xdist")
    return True


def resolve_xdist_group(item: pytest.Item) -> str | None:
    """Return the logical xdist group for a collected test item."""

    keywords = item.keywords
    if "db" in keywords or "schema" in keywords:
        return "database"

    if "network" in keywords:
        return "network"

    if "gpu" in keywords:
        return "ml"

    item_path = Path(str(getattr(item, "path", getattr(item, "fspath", ""))))
    lower_parts = {part.lower() for part in item_path.parts}
    if "ml" in lower_parts or "gpu" in lower_parts:
        return "ml"

    return None


def ensure_cli_opt_in(request: pytest.FixtureRequest, *, option: str, marker: str) -> None:
    """Skip costly fixtures unless explicitly enabled via CLI flag."""

    if request.config.getoption(option):
        return

    cli_flag = option.replace("_", "-")
    pytest.skip(
        f"@pytest.mark.{marker} fixtures require the --{cli_flag} flag; "
        f"rerun with --{cli_flag} to enable this opt-in suite."
    )


__all__ = [
    "FIXTURE_MARKER_REQUIREMENTS",
    "MARKER_OPTIONS",
    "ensure_cli_opt_in",
    "ensure_project_root_on_path",
    "register_randomly_plugin",
    "register_xdist_plugin",
    "resolve_xdist_group",
]
