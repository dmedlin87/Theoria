"""LLM registry backed by the settings store."""

from __future__ import annotations

from sqlalchemy.orm import Session

from theo.application.facades.settings_store import load_setting, save_setting
from theo.application.ports.ai_registry import (
    GenerationError,
    LLMModel,
    LLMRegistry,
    SECRET_CONFIG_KEYS,
    SETTINGS_KEY,
    registry_from_payload,
)


def get_llm_registry(session: Session) -> LLMRegistry:
    payload = load_setting(session, SETTINGS_KEY, default=None)
    registry, migrated = registry_from_payload(payload if isinstance(payload, dict) else None)
    if migrated:
        save_llm_registry(session, registry)
    return registry


def save_llm_registry(session: Session, registry: LLMRegistry) -> None:
    save_setting(session, SETTINGS_KEY, registry.serialize())


__all__ = [
    "GenerationError",
    "LLMModel",
    "LLMRegistry",
    "SECRET_CONFIG_KEYS",
    "SETTINGS_KEY",
    "get_llm_registry",
    "save_llm_registry",
]
