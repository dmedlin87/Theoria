"""LLM registry backed by the settings store."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..core.settings_store import load_setting, save_setting
from .clients import GenerationError, LanguageModelClient, build_client

SETTINGS_KEY = "llm"


@dataclass
class LLMModel:
    name: str
    provider: str
    model: str
    config: dict[str, Any] = field(default_factory=dict)

    def masked_api_key(self) -> str | None:
        key = self.config.get("api_key")
        if not key or not isinstance(key, str):
            return None
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:4]}…{key[-4:]}"

    def to_payload(self, include_secret: bool = False) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "config": {
                k: v for k, v in self.config.items() if include_secret or k != "api_key"
            },
        }
        if not include_secret and self.config.get("api_key"):
            payload["masked_api_key"] = self.masked_api_key()
        return payload

    def build_client(self) -> LanguageModelClient:
        return build_client(self.provider, self.config)


@dataclass
class LLMRegistry:
    models: dict[str, LLMModel] = field(default_factory=dict)
    default_model: str | None = None

    def add_model(self, model: LLMModel, *, make_default: bool = False) -> None:
        self.models[model.name] = model
        if make_default or not self.default_model:
            self.default_model = model.name

    def remove_model(self, name: str) -> None:
        if name in self.models:
            del self.models[name]
        if self.default_model == name:
            self.default_model = next(iter(self.models), None)

    def get(self, name: str | None = None) -> LLMModel:
        if name is None:
            if not self.default_model:
                raise GenerationError("No default model configured")
            name = self.default_model
        model = self.models.get(name)
        if model is None:
            raise GenerationError(f"Unknown model: {name}")
        return model

    def serialize(self) -> dict[str, Any]:
        return {
            "default_model": self.default_model,
            "models": [
                model.to_payload(include_secret=True) for model in self.models.values()
            ],
        }

    def to_response(self) -> dict[str, Any]:
        return {
            "default_model": self.default_model,
            "models": [model.to_payload() for model in self.models.values()],
        }


def _load_bootstrap_models() -> Iterable[LLMModel]:
    settings = get_settings()
    for name, payload in settings.llm_models.items():
        if not isinstance(payload, dict):
            continue
        provider = str(payload.get("provider", "openai"))
        model_name = str(payload.get("model", name))
        config = {k: v for k, v in payload.items() if k not in {"provider", "model"}}
        if provider == "openai" and "api_key" not in config:
            if settings.openai_api_key:
                config.setdefault("api_key", settings.openai_api_key)
            if settings.openai_base_url:
                config.setdefault("base_url", settings.openai_base_url)
        yield LLMModel(name=name, provider=provider, model=model_name, config=config)


def _registry_from_payload(payload: dict[str, Any] | None) -> LLMRegistry:
    registry = LLMRegistry()
    if payload:
        models = payload.get("models", [])
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name"))
            provider = str(item.get("provider", "openai"))
            model_name = str(item.get("model", name))
            config = item.get("config", {}) or {}
            if not name:
                continue
            registry.add_model(
                LLMModel(name=name, provider=provider, model=model_name, config=config)
            )
        default_model = payload.get("default_model")
        if isinstance(default_model, str):
            registry.default_model = default_model
    if not registry.models:
        for model in _load_bootstrap_models():
            registry.add_model(model)
        if settings := get_settings():
            if settings.llm_default_model:
                registry.default_model = settings.llm_default_model
    return registry


def get_llm_registry(session: Session) -> LLMRegistry:
    payload = load_setting(session, SETTINGS_KEY, default=None)
    return _registry_from_payload(payload if isinstance(payload, dict) else None)


def save_llm_registry(session: Session, registry: LLMRegistry) -> None:
    save_setting(session, SETTINGS_KEY, registry.serialize())


__all__ = [
    "LLMModel",
    "LLMRegistry",
    "GenerationError",
    "get_llm_registry",
    "save_llm_registry",
]
