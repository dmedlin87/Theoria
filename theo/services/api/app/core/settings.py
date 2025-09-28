"""Application configuration for the Theo Engine API."""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="", env_file=".env", env_file_encoding="utf-8"
    )

    database_url: str = Field(
        default="sqlite:///./theo.db", description="SQLAlchemy database URL"
    )
    redis_url: str = Field(
        default="redis://redis:6379/0", description="Celery broker URL"
    )
    storage_root: Path = Field(
        default=Path("./storage"), description="Location for persisted artifacts"
    )
    embedding_model: str = Field(default="BAAI/bge-m3")
    embedding_dim: int = Field(default=1024)
    max_chunk_tokens: int = Field(default=900)
    doc_max_pages: int = Field(default=5000)
    transcript_max_window: float = Field(default=40.0)
    fixtures_root: Path | None = Field(
        default=None, description="Optional fixtures path for offline resources"
    )
    user_agent: str = Field(default="TheoEngine/1.0")
    llm_default_model: str | None = Field(
        default=None, description="Default model identifier for generative features"
    )
    llm_models: dict[str, dict[str, object]] = Field(
        default_factory=dict,
        description="Bootstrap LLM model definitions loaded from the environment.",
    )
    openai_api_key: str | None = Field(
        default=None, description="Optional OpenAI API key"
    )
    openai_base_url: str | None = Field(
        default=None, description="Override base URL for OpenAI-compatible APIs"
    )
    notification_webhook_url: str | None = Field(
        default=None,
        description="Endpoint for dispatching notification webhooks",
    )
    notification_webhook_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Additional HTTP headers applied to webhook notifications",
    )
    notification_timeout_seconds: float = Field(
        default=10.0, description="HTTP timeout when delivering notifications"
    )
    settings_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SETTINGS_SECRET_KEY", "settings_secret_key"),
        description="Secret used to derive the Fernet key for persisted settings",
    )
    api_keys: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("THEO_API_KEYS", "API_KEYS"),
        description="List of accepted API keys for first-party integrations",
    )
    auth_jwt_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("THEO_AUTH_JWT_SECRET", "AUTH_JWT_SECRET"),
        description="Shared secret used to validate bearer JWTs",
    )
    auth_jwt_audience: str | None = Field(
        default=None,
        validation_alias=AliasChoices("THEO_AUTH_JWT_AUDIENCE", "AUTH_JWT_AUDIENCE"),
        description="Optional audience claim enforced for JWT authentication",
    )
    auth_jwt_issuer: str | None = Field(
        default=None,
        validation_alias=AliasChoices("THEO_AUTH_JWT_ISSUER", "AUTH_JWT_ISSUER"),
        description="Optional issuer claim enforced for JWT authentication",
    )
    auth_jwt_algorithms: list[str] = Field(
        default_factory=lambda: ["HS256"],
        validation_alias=AliasChoices(
            "THEO_AUTH_JWT_ALGORITHMS", "AUTH_JWT_ALGORITHMS"
        ),
        description="Allowed signing algorithms for validating JWTs",
    )

    @field_validator("api_keys", mode="before")
    @classmethod
    def _parse_api_keys(cls, value: object) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [segment.strip() for segment in value.split(",") if segment.strip()]
        if isinstance(value, list):
            return value
        raise ValueError("Invalid API key configuration")

    @field_validator("auth_jwt_algorithms", mode="before")
    @classmethod
    def _parse_algorithms(cls, value: object) -> list[str]:
        if value in (None, ""):
            return ["HS256"]
        if isinstance(value, str):
            parsed = [segment.strip() for segment in value.split(",") if segment.strip()]
            return parsed or ["HS256"]
        if isinstance(value, list):
            return value
        raise ValueError("Invalid JWT algorithm configuration")
    contradictions_enabled: bool = Field(
        default=True, description="Toggle contradiction search endpoints"
    )
    geo_enabled: bool = Field(
        default=True, description="Toggle geography lookup endpoints"
    )
    creator_verse_perspectives_enabled: bool = Field(
        default=True,
        description="Toggle aggregated creator perspectives by verse",
    )
    creator_verse_rollups_async_refresh: bool = Field(
        default=False,
        description="Queue creator verse rollup refreshes via Celery instead of inline",
    )
    verse_timeline_enabled: bool = Field(
        default=True,
        description="Toggle verse mention timeline aggregation endpoints",
    )
    ingest_upload_max_bytes: int = Field(
        default=16 * 1024 * 1024,
        description="Maximum allowed size for synchronous ingest uploads in bytes",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    settings = Settings()
    if settings.fixtures_root is None:
        candidate = Path(__file__).resolve().parents[5] / "fixtures"
        if candidate.exists():
            settings.fixtures_root = candidate

    return settings


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def get_settings_cipher() -> Fernet | None:
    """Return a cached Fernet instance for encrypting persisted settings."""

    secret = get_settings().settings_secret_key
    if not secret:
        return None
    return Fernet(_derive_fernet_key(secret))
