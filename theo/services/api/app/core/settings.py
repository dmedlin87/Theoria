"""Application configuration."""

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    database_url: str = Field(env="DATABASE_URL", default="postgresql+psycopg://postgres:postgres@db:5432/theo")
    redis_url: str = Field(env="REDIS_URL", default="redis://redis:6379/0")
    storage_root: str = Field(env="STORAGE_ROOT", default="/data/storage")


settings = Settings()
