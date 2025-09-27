"""Persistence helpers for dynamic application settings."""

from __future__ import annotations

import json
import logging
from typing import Any

from cryptography.fernet import InvalidToken
from sqlalchemy.orm import Session

from ..db.models import AppSetting
from .settings import get_settings_cipher

SETTINGS_NAMESPACE = "app"
_ENCRYPTED_FIELD = "__encrypted__"

logger = logging.getLogger(__name__)


class SettingNotFoundError(KeyError):
    """Raised when a requested setting is unavailable."""


def _qualify(key: str) -> str:
    if key.startswith(f"{SETTINGS_NAMESPACE}:"):
        return key
    return f"{SETTINGS_NAMESPACE}:{key}"


def load_setting(session: Session, key: str, default: Any | None = None) -> Any | None:
    """Return the stored value for ``key`` or ``default`` when missing."""

    qualified = _qualify(key)
    record = session.get(AppSetting, qualified)
    if record is None:
        return default
    return _decrypt_value(record.value, qualified)


def require_setting(session: Session, key: str) -> Any:
    """Return the stored value for ``key`` raising when missing."""

    qualified = _qualify(key)
    record = session.get(AppSetting, qualified)
    if record is None:
        raise SettingNotFoundError(key)
    return _decrypt_value(record.value, qualified)


def save_setting(session: Session, key: str, value: Any | None) -> None:
    """Persist ``value`` for ``key`` within the shared namespace."""

    qualified = _qualify(key)
    record = session.get(AppSetting, qualified)
    if record is None:
        record = AppSetting(key=qualified, value=_encrypt_value(value))
    else:
        record.value = _encrypt_value(value)
    session.add(record)
    session.commit()


def _encrypt_value(value: Any | None) -> Any | None:
    cipher = get_settings_cipher()
    if cipher is None:
        return value
    payload = json.dumps(value, separators=(",", ":"))
    token = cipher.encrypt(payload.encode("utf-8")).decode("utf-8")
    return {_ENCRYPTED_FIELD: token}


def _decrypt_value(value: Any | None, key: str) -> Any | None:
    if not isinstance(value, dict) or _ENCRYPTED_FIELD not in value:
        return value
    cipher = get_settings_cipher()
    if cipher is None:
        raise RuntimeError(
            "SETTINGS_SECRET_KEY is required to decrypt persisted setting"
        )
    token = value[_ENCRYPTED_FIELD]
    try:
        decrypted = cipher.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        logger.error("Failed to decrypt setting %s", key)
        raise RuntimeError("Failed to decrypt persisted setting") from exc
    return json.loads(decrypted)


__all__ = [
    "SETTINGS_NAMESPACE",
    "SettingNotFoundError",
    "load_setting",
    "require_setting",
    "save_setting",
]
