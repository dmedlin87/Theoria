"""Application-level primitives for the LLM registry."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

try:  # pragma: no cover - optional dependency in lightweight tests
    from cryptography.fernet import InvalidToken
except ModuleNotFoundError:  # pragma: no cover - provide fallback sentinel
    class InvalidToken(Exception):
        pass

from theo.application.facades.settings import get_settings, get_settings_cipher
from theo.application.interfaces import LanguageModelClientProtocol

SETTINGS_KEY = "llm"
SECRET_CONFIG_KEYS = {
    "api_key",
    "access_token",
    "credentials",
    "credentials_json",
    "service_account",
    "service_account_key",
}
_ENCRYPTED_FIELD = "__encrypted__"

logger = logging.getLogger(__name__)


ClientFactory = Callable[[str, dict[str, Any]], LanguageModelClientProtocol]


class GenerationError(RuntimeError):
    """Raised when a provider fails to generate content."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


def _normalize_metadata(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items()}


@dataclass
class LLMModel:
    name: str
    provider: str
    model: str
    config: dict[str, Any] = field(default_factory=dict)
    pricing: dict[str, Any] = field(default_factory=dict)
    latency: dict[str, Any] = field(default_factory=dict)
    routing: dict[str, Any] = field(default_factory=dict)
    client_factory: ClientFactory | None = field(
        default=None, repr=False, compare=False
    )

    def masked_api_key(self) -> str | None:
        for key_name in SECRET_CONFIG_KEYS:
            secret = self.config.get(key_name)
            if not secret or not isinstance(secret, str):
                continue
            if len(secret) <= 8:
                return "*" * len(secret)
            return f"{secret[:4]}…{secret[-4:]}"
        return None

    def to_payload(self, include_secret: bool = False) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "config": {
                k: v
                for k, v in self.config.items()
                if include_secret or k not in SECRET_CONFIG_KEYS
            },
        }
        if self.pricing:
            payload["pricing"] = dict(self.pricing)
        if self.latency:
            payload["latency"] = dict(self.latency)
        if self.routing:
            payload["routing"] = dict(self.routing)
        if not include_secret and self.masked_api_key():
            payload["masked_api_key"] = self.masked_api_key()
        return payload

    def build_client(self) -> LanguageModelClientProtocol:
        if self.client_factory is None:
            raise RuntimeError(
                "Language model client factory has not been configured. "
                "Provide one via LLMRegistry(client_factory=...), "
                "registry_from_payload(client_factory=...), or "
                "LLMRegistry.set_client_factory(...)."
            )
        return self.client_factory(self.provider, self.config)


@dataclass
class LLMRegistry:
    models: dict[str, LLMModel] = field(default_factory=dict)
    default_model: str | None = None
    client_factory: ClientFactory | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if self.client_factory is not None:
            for model in self.models.values():
                model.client_factory = self.client_factory

    def add_model(self, model: LLMModel, *, make_default: bool = False) -> None:
        if self.client_factory is not None:
            model.client_factory = self.client_factory
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
                {
                    "name": model.name,
                    "provider": model.provider,
                    "model": model.model,
                    "config": encrypt_config(model.config),
                    "pricing": dict(model.pricing),
                    "latency": dict(model.latency),
                    "routing": dict(model.routing),
                }
                for model in self.models.values()
            ],
        }

    def to_response(self) -> dict[str, Any]:
        return {
            "default_model": self.default_model,
            "models": [model.to_payload() for model in self.models.values()],
        }

    def set_client_factory(self, factory: ClientFactory | None) -> None:
        self.client_factory = factory
        for model in self.models.values():
            model.client_factory = factory


def _load_bootstrap_models(
    client_factory: ClientFactory | None,
) -> Iterable[LLMModel]:
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
        yield LLMModel(
            name=name,
            provider=provider,
            model=model_name,
            config=config,
            client_factory=client_factory,
        )


def registry_from_payload(
    payload: dict[str, Any] | None,
    *,
    client_factory: ClientFactory | None = None,
    registry_cls: type[LLMRegistry] = LLMRegistry,
    model_cls: type[LLMModel] = LLMModel,
) -> tuple[LLMRegistry, bool]:
    registry = registry_cls(client_factory=client_factory)
    migrated = False
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
            decrypted_config, was_plaintext = decrypt_config(config)
            migrated = migrated or was_plaintext
            pricing = item.get("pricing") if isinstance(item, dict) else None
            latency = item.get("latency") if isinstance(item, dict) else None
            routing = item.get("routing") if isinstance(item, dict) else None
            registry.add_model(
                model_cls(
                    name=name,
                    provider=provider,
                    model=model_name,
                    config=decrypted_config,
                    pricing=_normalize_metadata(pricing),
                    latency=_normalize_metadata(latency),
                    routing=_normalize_metadata(routing),
                    client_factory=client_factory,
                )
            )
        default_model = payload.get("default_model")
        if isinstance(default_model, str):
            registry.default_model = default_model
    if not registry.models:
        for model in _load_bootstrap_models(client_factory):
            registry.add_model(model)
        if settings := get_settings():
            if settings.llm_default_model:
                registry.default_model = settings.llm_default_model
    return registry, migrated


def encrypt_config(config: dict[str, Any]) -> dict[str, Any]:
    """Encrypt sensitive configuration values while preserving structure.
    
    Args:
        config: Configuration dictionary to encrypt
        
    Returns:
        Dictionary with sensitive values encrypted
        
    Raises:
        RuntimeError: When encryption is required but SETTINGS_SECRET_KEY not configured
    """
    cipher = get_settings_cipher()
    encrypted: dict[str, Any] = {}
    
    for key, value in config.items():
        if (
            cipher
            and key in SECRET_CONFIG_KEYS
            and isinstance(value, str)
            and value
        ):
            token = cipher.encrypt(value.encode("utf-8")).decode("utf-8")
            encrypted[key] = {_ENCRYPTED_FIELD: token}
        else:
            if (
                cipher is None
                and key in SECRET_CONFIG_KEYS
                and isinstance(value, str)
                and value
            ):
                # Use generic error message that doesn't reveal key names
                logger.error(
                    "Cannot persist secrets without SETTINGS_SECRET_KEY. "
                    "Set the environment variable before updating the registry."
                )
                raise RuntimeError(
                    "SETTINGS_SECRET_KEY must be configured to store secrets"
                )
            encrypted[key] = value
    return encrypted


def decrypt_config(config: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Decrypt sensitive configuration values.
    
    Args:
        config: Configuration dictionary potentially containing encrypted values
        
    Returns:
        Tuple of (decrypted_config, was_migrated_from_plaintext)
        
    Raises:
        GenerationError: When decryption fails or secret key is missing
    """
    cipher = get_settings_cipher()
    decrypted: dict[str, Any] = {}
    migrated = False
    
    for key, value in config.items():
        if isinstance(value, dict) and _ENCRYPTED_FIELD in value:
            if cipher is None:
                raise GenerationError(
                    "Configuration decryption requires SETTINGS_SECRET_KEY"
                )
            token = value[_ENCRYPTED_FIELD]
            try:
                decrypted_bytes = cipher.decrypt(token.encode("utf-8"))
                decrypted_value = decrypted_bytes.decode("utf-8")
                # Clear the decrypted bytes from memory
                del decrypted_bytes
            except InvalidToken as exc:
                # Use generic error message that doesn't reveal system details
                raise GenerationError("Configuration decryption failed") from exc
            except Exception as exc:
                # Catch any other decryption-related errors
                raise GenerationError("Configuration decryption failed") from exc
                
            decrypted[key] = decrypted_value
            continue
            
        decrypted[key] = value
        if (
            cipher
            and key in SECRET_CONFIG_KEYS
            and isinstance(value, str)
            and value
        ):
            migrated = True
            
    return decrypted, migrated


def _secure_clear_dict(data: dict[str, Any]) -> None:
    """Securely clear sensitive data from dictionary in memory."""
    for key in list(data.keys()):
        if key in SECRET_CONFIG_KEYS and isinstance(data[key], str):
            # Overwrite the string value in memory before deleting
            original_value = data[key]
            data[key] = "*" * len(original_value)
            del data[key]


LanguageModelClient = LanguageModelClientProtocol

__all__ = [
    "ClientFactory",
    "GenerationError",
    "LLMModel",
    "LLMRegistry",
    "SECRET_CONFIG_KEYS",
    "SETTINGS_KEY",
    "decrypt_config",
    "encrypt_config",
    "registry_from_payload",
    "LanguageModelClient",
    "LanguageModelClientProtocol",
]
