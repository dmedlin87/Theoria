"""Configuration management for MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ServerConfig:
    """MCP server configuration."""

    # Server metadata
    name: str = "theo-mcp-server"
    version: str = "0.1.0"
    environment: str = "production"

    # Feature flags
    tools_enabled: bool = True
    metrics_enabled: bool = True
    debug: bool = False

    # Security settings
    max_request_body_size: int = 10 * 1024 * 1024  # 10MB
    cors_allow_origins: List[str] | None = None
    cors_allow_credentials: bool = True

    # Schema configuration
    schema_base_url: str = "https://theoengine.dev/mcp/schemas"

    # Rate limiting
    default_rate_limit_window_seconds: int = 60

    # Request timeouts
    request_timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> ServerConfig:
        """Load configuration from environment variables."""
        return cls(
            environment=os.getenv("MCP_ENVIRONMENT", "production"),
            tools_enabled=_parse_bool(os.getenv("MCP_TOOLS_ENABLED")),
            metrics_enabled=_parse_bool(
                os.getenv("MCP_METRICS_ENABLED", "true")
            ),
            debug=_parse_bool(os.getenv("MCP_DEBUG", "false")),
            max_request_body_size=_parse_int(
                os.getenv("MCP_MAX_REQUEST_SIZE"), 10 * 1024 * 1024
            ),
            cors_allow_origins=_parse_list(os.getenv("MCP_CORS_ORIGINS")),
            cors_allow_credentials=_parse_bool(
                os.getenv("MCP_CORS_CREDENTIALS", "true")
            ),
            schema_base_url=(
                os.getenv("MCP_SCHEMA_BASE_URL", "https://theoengine.dev/mcp/schemas")
                .rstrip("/")
            ),
            request_timeout_seconds=_parse_int(
                os.getenv("MCP_REQUEST_TIMEOUT"), 30
            ),
        )


def _parse_bool(value: str | None, default: bool = False) -> bool:
    """Parse boolean value from string."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int = 0) -> int:
    """Parse integer value from string."""
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _parse_list(value: str | None) -> List[str] | None:
    """Parse comma-separated list from string."""
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


__all__ = ["ServerConfig"]
