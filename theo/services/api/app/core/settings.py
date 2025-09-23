"""Application configuration for the Theo Engine API."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", env_file_encoding="utf-8")

    database_url: str = Field(
        default="sqlite:///./theo.db", description="SQLAlchemy database URL"
    )
    redis_url: str = Field(default="redis://redis:6379/0", description="Celery broker URL")
    storage_root: Path = Field(default=Path("./storage"), description="Location for persisted artifacts")
    embedding_model: str = Field(default="BAAI/bge-m3")
    embedding_dim: int = Field(default=1024)
    max_chunk_tokens: int = Field(default=900)
    doc_max_pages: int = Field(default=5000)
    user_agent: str = Field(default="TheoEngine/1.0")

@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    settings = Settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
