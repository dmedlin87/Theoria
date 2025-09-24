"""Persistence helpers for dynamic application settings."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..db.models import AppSetting

SETTINGS_NAMESPACE = "app"


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
    return record.value


def require_setting(session: Session, key: str) -> Any:
    """Return the stored value for ``key`` raising when missing."""

    qualified = _qualify(key)
    record = session.get(AppSetting, qualified)
    if record is None:
        raise SettingNotFoundError(key)
    return record.value


def save_setting(session: Session, key: str, value: Any | None) -> None:
    """Persist ``value`` for ``key`` within the shared namespace."""

    qualified = _qualify(key)
    record = session.get(AppSetting, qualified)
    if record is None:
        record = AppSetting(key=qualified, value=value)
    else:
        record.value = value
    session.add(record)
    session.commit()


__all__ = [
    "SETTINGS_NAMESPACE",
    "SettingNotFoundError",
    "load_setting",
    "require_setting",
    "save_setting",
]
