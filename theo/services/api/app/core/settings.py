"""Application configuration for the Theo Engine API."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
    contradictions_enabled: bool = Field(
        default=True, description="Toggle contradiction search endpoints"
    )
    geo_enabled: bool = Field(
        default=True, description="Toggle geography lookup endpoints"
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
