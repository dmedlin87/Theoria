"""Compatibility facades exposing application-layer entry points.

These modules provide forward-looking import paths for adapters while the
legacy implementation continues to live under ``theo.services``. Once the
migration completes, adapters can depend exclusively on the application
package without touching service-specific modules.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "database",
    "research",
    "runtime",
    "secret_migration",
    "settings",
    "settings_store",
    "version",
    "Base",
    "configure_engine",
    "get_engine",
    "get_session",
    "allow_insecure_startup",
    "ResearchService",
    "ResearchNoteDraft",
    "ResearchNoteEvidenceDraft",
    "get_research_service",
    "migrate_secret_settings",
    "Settings",
    "get_settings",
    "get_settings_secret",
    "get_settings_cipher",
    "SETTINGS_NAMESPACE",
    "SettingNotFoundError",
    "load_setting",
    "require_setting",
    "save_setting",
    "get_git_sha",
]

_MODULE_EXPORTS = {
    "database": "theo.application.facades.database",
    "research": "theo.application.facades.research",
    "runtime": "theo.application.facades.runtime",
    "secret_migration": "theo.application.facades.secret_migration",
    "settings": "theo.application.facades.settings",
    "settings_store": "theo.application.facades.settings_store",
    "version": "theo.application.facades.version",
}

_ATTRIBUTE_EXPORTS = {
    "Base": ("theo.application.facades.database", "Base"),
    "configure_engine": ("theo.application.facades.database", "configure_engine"),
    "get_engine": ("theo.application.facades.database", "get_engine"),
    "get_session": ("theo.application.facades.database", "get_session"),
    "allow_insecure_startup": (
        "theo.application.facades.runtime",
        "allow_insecure_startup",
    ),
    "ResearchService": (
        "theo.application.facades.research",
        "ResearchService",
    ),
    "ResearchNoteDraft": (
        "theo.application.facades.research",
        "ResearchNoteDraft",
    ),
    "ResearchNoteEvidenceDraft": (
        "theo.application.facades.research",
        "ResearchNoteEvidenceDraft",
    ),
    "get_research_service": (
        "theo.application.facades.research",
        "get_research_service",
    ),
    "migrate_secret_settings": (
        "theo.application.facades.secret_migration",
        "migrate_secret_settings",
    ),
    "Settings": ("theo.application.facades.settings", "Settings"),
    "get_settings": ("theo.application.facades.settings", "get_settings"),
    "get_settings_secret": (
        "theo.application.facades.settings",
        "get_settings_secret",
    ),
    "get_settings_cipher": (
        "theo.application.facades.settings",
        "get_settings_cipher",
    ),
    "SETTINGS_NAMESPACE": (
        "theo.application.facades.settings_store",
        "SETTINGS_NAMESPACE",
    ),
    "SettingNotFoundError": (
        "theo.application.facades.settings_store",
        "SettingNotFoundError",
    ),
    "load_setting": ("theo.application.facades.settings_store", "load_setting"),
    "require_setting": (
        "theo.application.facades.settings_store",
        "require_setting",
    ),
    "save_setting": ("theo.application.facades.settings_store", "save_setting"),
    "get_git_sha": ("theo.application.facades.version", "get_git_sha"),
}


def __getattr__(name: str) -> Any:
    if name in _MODULE_EXPORTS:
        module = import_module(_MODULE_EXPORTS[name])
        globals()[name] = module
        return module
    if name in _ATTRIBUTE_EXPORTS:
        module_name, attribute = _ATTRIBUTE_EXPORTS[name]
        module = import_module(module_name)
        value = getattr(module, attribute)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
