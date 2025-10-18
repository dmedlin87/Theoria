"""LLM registry backed by the settings store."""

from __future__ import annotations

from sqlalchemy.orm import Session

from theo.application.facades.settings_store import load_setting, save_setting
from theo.application.ports.ai_registry import (
    GenerationError,
    LLMModel as ApplicationLLMModel,
    LLMRegistry as ApplicationLLMRegistry,
    SECRET_CONFIG_KEYS,
    SETTINGS_KEY,
    registry_from_payload as application_registry_from_payload,
)

from .clients import build_client


class LLMModel(ApplicationLLMModel):
    """Service-level model wired with the default client factory."""

    def __init__(self, *args, client_factory=None, **kwargs):
        factory = client_factory if client_factory is not None else build_client
        super().__init__(*args, client_factory=factory, **kwargs)


class LLMRegistry(ApplicationLLMRegistry):
    """Service-level registry preconfigured with the default client factory."""

    def __init__(self, *args, client_factory=None, **kwargs):
        factory = client_factory if client_factory is not None else build_client
        super().__init__(*args, client_factory=factory, **kwargs)


def get_llm_registry(session: Session) -> LLMRegistry:
    payload = load_setting(session, SETTINGS_KEY, default=None)
    registry, migrated = application_registry_from_payload(
        payload if isinstance(payload, dict) else None,
        registry_cls=LLMRegistry,
        model_cls=LLMModel,
    )
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
