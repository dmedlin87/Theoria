"""Persistence helpers for dynamic application settings."""

from __future__ import annotations

import json
import logging
from typing import Any

try:  # pragma: no cover - cryptography optional in lightweight tests
    from cryptography.fernet import Fernet, InvalidToken
except ModuleNotFoundError:  # pragma: no cover - provide sentinel fallbacks
    class InvalidToken(Exception):
        pass

    class Fernet:  # type: ignore[override]
        def __init__(self, *_args, **_kwargs) -> None:
            raise ModuleNotFoundError(
                "cryptography is required for Fernet secrets support"
            )

        def encrypt(self, *_args, **_kwargs):  # pragma: no cover - defensive
            raise ModuleNotFoundError(
                "cryptography is required for Fernet secrets support"
            )

        def decrypt(self, *_args, **_kwargs):  # pragma: no cover - defensive
            raise ModuleNotFoundError(
                "cryptography is required for Fernet secrets support"
            )

from theo.adapters.persistence.models import AppSetting
from theo.application.facades.settings import get_settings_cipher
from theo.application.interfaces import SessionProtocol

SETTINGS_NAMESPACE = "app"
_ENCRYPTED_FIELD = "__encrypted__"
_SECRET_HINT_FIELDS = {
    "api_key",
    "access_token",
    "credentials",
    "credentials_json",
    "service_account",
    "service_account_key",
}

logger = logging.getLogger(__name__)


class SettingNotFoundError(KeyError):
    """Raised when a requested setting is unavailable."""


def _qualify(key: str) -> str:
    if key.startswith(f"{SETTINGS_NAMESPACE}:"):
        return key
    return f"{SETTINGS_NAMESPACE}:{key}"


def load_setting(
    session: SessionProtocol, key: str, default: Any | None = None
) -> Any | None:
    """Return the stored value for ``key`` or ``default`` when missing."""

    qualified = _qualify(key)
    record = session.get(AppSetting, qualified)
    if record is None:
        return default
    cipher = get_settings_cipher()
    _ensure_cipher_available(qualified, record.value, cipher)
    return _decrypt_value(record.value, qualified, cipher)


def require_setting(session: SessionProtocol, key: str) -> Any:
    """Return the stored value for ``key`` raising when missing."""

    qualified = _qualify(key)
    record = session.get(AppSetting, qualified)
    if record is None:
        raise SettingNotFoundError(key)
    cipher = get_settings_cipher()
    _ensure_cipher_available(qualified, record.value, cipher)
    return _decrypt_value(record.value, qualified, cipher)


def save_setting(session: SessionProtocol, key: str, value: Any | None) -> None:
    """Persist ``value`` for ``key`` within the shared namespace."""

    qualified = _qualify(key)
    cipher = get_settings_cipher()
    _ensure_cipher_available(qualified, value, cipher)
    record = session.get(AppSetting, qualified)
    if record is None:
        record = AppSetting(key=qualified, value=_encrypt_value(value, cipher))
    else:
        record.value = _encrypt_value(value, cipher)
    session.add(record)
    session.commit()


def _encrypt_value(value: Any | None, cipher: Fernet | None = None) -> Any | None:
    cipher = cipher if cipher is not None else get_settings_cipher()
    if cipher is None:
        return value
    payload = json.dumps(value, separators=(",", ":"))
    token = cipher.encrypt(payload.encode("utf-8")).decode("utf-8")
    return {_ENCRYPTED_FIELD: token}


def _decrypt_value(
    value: Any | None, key: str, cipher: Fernet | None = None
) -> Any | None:
    if not isinstance(value, dict) or _ENCRYPTED_FIELD not in value:
        return value
    cipher = cipher if cipher is not None else get_settings_cipher()
    if cipher is None:
        logger.error(
            "Refusing to decrypt %s without SETTINGS_SECRET_KEY. Set the "
            "environment variable and restart the service.",
            key,
        )
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


def _ensure_cipher_available(
    key: str, value: Any | None, cipher: Fernet | None
) -> None:
    if cipher is not None:
        return
    if isinstance(value, dict) and _ENCRYPTED_FIELD in value:
        logger.error(
            "SETTINGS_SECRET_KEY is required before accessing %s. Set the "
            "environment variable to decrypt existing settings.",
            key,
        )
        raise RuntimeError(
            "SETTINGS_SECRET_KEY is required to decrypt persisted setting"
        )
    if _contains_secret_fields(value):
        logger.error(
            "SETTINGS_SECRET_KEY must be configured before working with %s. "
            "Set the environment variable or disable the related feature.",
            key,
        )
        raise RuntimeError(
            "SETTINGS_SECRET_KEY is required to store secret-bearing settings"
        )


def _contains_secret_fields(value: Any | None) -> bool:
    if isinstance(value, dict):
        for field, item in value.items():
            if field == _ENCRYPTED_FIELD and isinstance(item, str):
                return True
            if field in _SECRET_HINT_FIELDS and isinstance(item, str) and item:
                return True
            if _contains_secret_fields(item):
                return True
    elif isinstance(value, list):
        return any(_contains_secret_fields(item) for item in value)
    return False


__all__ = [
    "SETTINGS_NAMESPACE",
    "SettingNotFoundError",
    "load_setting",
    "require_setting",
    "save_setting",
]
