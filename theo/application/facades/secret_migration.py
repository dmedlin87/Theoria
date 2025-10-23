"""Utilities for migrating plaintext settings to encrypted storage."""

from __future__ import annotations

import logging
from typing import Any

from theo.adapters.persistence.models import AppSetting
from theo.application.facades.settings import get_settings_cipher
from theo.application.facades.settings_store import (
    SETTINGS_NAMESPACE,
    save_setting,
)
from theo.application.interfaces import SessionProtocol
from theo.application.ports.ai_registry import (
    SECRET_CONFIG_KEYS,
    SETTINGS_KEY as LLM_SETTINGS_KEY,
    registry_from_payload,
)
from theo.services.api.app.ai.registry import save_llm_registry

logger = logging.getLogger(__name__)

_ENCRYPTED_FIELD = "__encrypted__"
_PROVIDER_SETTINGS_KEY = "ai_providers"


def migrate_secret_settings(
    session: SessionProtocol, *, dry_run: bool = False
) -> list[str]:
    """Re-encrypt plaintext secrets stored in ``app_settings``."""

    cipher = get_settings_cipher()
    if cipher is None:
        raise RuntimeError(
            "SETTINGS_SECRET_KEY must be configured before migrating secret settings"
        )

    migrated: list[str] = []

    if _migrate_llm_registry(session, dry_run=dry_run):
        migrated.append(LLM_SETTINGS_KEY)
    if _migrate_provider_settings(session, dry_run=dry_run):
        migrated.append(_PROVIDER_SETTINGS_KEY)

    if migrated:
        logger.info("Re-encrypted settings: %s", ", ".join(migrated))
    else:
        logger.info("No plaintext settings required migration")

    return migrated


def _migrate_llm_registry(session: SessionProtocol, *, dry_run: bool) -> bool:
    record = session.get(AppSetting, _qualify(LLM_SETTINGS_KEY))
    if record is None:
        return False
    payload = record.value
    if not _contains_plaintext_llm(payload):
        return False
    if dry_run:
        return True
    registry, _ = registry_from_payload(payload if isinstance(payload, dict) else None)
    save_llm_registry(session, registry)
    return True


def _migrate_provider_settings(
    session: SessionProtocol, *, dry_run: bool
) -> bool:
    record = session.get(AppSetting, _qualify(_PROVIDER_SETTINGS_KEY))
    if record is None:
        return False
    payload = record.value
    if not _contains_plaintext_provider(payload):
        return False
    if dry_run:
        return True
    save_setting(session, _PROVIDER_SETTINGS_KEY, payload)
    return True


def _contains_plaintext_llm(value: Any | None) -> bool:
    if not isinstance(value, dict) or _ENCRYPTED_FIELD in value:
        return False
    models = value.get("models")
    if not isinstance(models, list):
        return False
    for item in models:
        if not isinstance(item, dict):
            continue
        config = item.get("config")
        if not isinstance(config, dict):
            continue
        for key in SECRET_CONFIG_KEYS:
            secret_value = config.get(key)
            if isinstance(secret_value, str) and secret_value:
                return True
    return False


def _contains_plaintext_provider(value: Any | None) -> bool:
    if not isinstance(value, dict) or _ENCRYPTED_FIELD in value:
        return False
    for payload in value.values():
        if not isinstance(payload, dict):
            continue
        api_key = payload.get("api_key")
        if isinstance(api_key, str) and api_key:
            return True
    return False


def _qualify(key: str) -> str:
    if key.startswith(f"{SETTINGS_NAMESPACE}:"):
        return key
    return f"{SETTINGS_NAMESPACE}:{key}"


__all__ = ["migrate_secret_settings"]
