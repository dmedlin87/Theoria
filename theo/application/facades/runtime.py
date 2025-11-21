"""Runtime feature flags for Theo Engine startup behaviours."""

from __future__ import annotations

import logging
import os
import secrets
from functools import lru_cache

LOGGER = logging.getLogger(__name__)

_GENERATED_DEV_KEY: str | None = None

_TRUTHY_VALUES = {"1", "true", "yes", "on"}
_ALLOWED_INSECURE_ENVIRONMENTS = {
    "development",
    "dev",
    "local",
    "test",
    "testing",
}
_DEFAULT_ENVIRONMENT = "production"


def _resolve_environment() -> str:
    """Return the current deployment environment label."""

    candidates = (
        os.getenv("THEORIA_ENVIRONMENT"),
        os.getenv("THEO_ENVIRONMENT"),
        os.getenv("ENVIRONMENT"),
        os.getenv("THEORIA_PROFILE"),
    )
    for candidate in candidates:
        if candidate:
            return candidate.strip().lower()
    return _DEFAULT_ENVIRONMENT


@lru_cache(maxsize=1)
def allow_insecure_startup() -> bool:
    """Return True when insecure startup overrides are permitted."""

    value = os.getenv("THEO_ALLOW_INSECURE_STARTUP", "")
    if value.lower() not in _TRUTHY_VALUES:
        return False

    environment = _resolve_environment()
    if environment not in _ALLOWED_INSECURE_ENVIRONMENTS:
        message = (
            "THEO_ALLOW_INSECURE_STARTUP is restricted to development and test "
            "environments. Set THEORIA_ENVIRONMENT=development (or disable the "
            "override) before starting the service. Current environment: %s"
        )
        LOGGER.critical(message, environment or _DEFAULT_ENVIRONMENT)
        raise RuntimeError(message % (environment or _DEFAULT_ENVIRONMENT))

    return True


def current_runtime_environment() -> str:
    """Expose the resolved runtime environment label for diagnostics."""

    return _resolve_environment()


def is_development_environment() -> bool:
    """Return True if running in a development or test environment."""
    environment = _resolve_environment()
    return environment in _ALLOWED_INSECURE_ENVIRONMENTS


def generate_ephemeral_dev_key() -> str | None:
    """Generate and return an ephemeral API key for development environments.

    This function generates a secure random API key when running in development
    environments without configured API keys. The key is generated once and cached
    for the lifetime of the process.

    Returns:
        A generated API key if in development environment, None otherwise.
    """
    global _GENERATED_DEV_KEY

    if not is_development_environment():
        return None

    if _GENERATED_DEV_KEY is not None:
        return _GENERATED_DEV_KEY

    # Generate a secure random key
    _GENERATED_DEV_KEY = f"dev-{secrets.token_urlsafe(32)}"

    # Log the key prominently so developers can use it
    LOGGER.warning(
        "\n"
        "═══════════════════════════════════════════════════════════════════════\n"
        "  AUTO-GENERATED DEVELOPMENT API KEY\n"
        "═══════════════════════════════════════════════════════════════════════\n"
        "  No API keys configured. Generated ephemeral key for this session:\n"
        "\n"
        "  %s\n"
        "\n"
        "  Use this key in your requests:\n"
        "    Authorization: Bearer %s\n"
        "\n"
        "  This key is valid only for this process lifetime.\n"
        "  Configure THEO_API_KEYS for persistent authentication.\n"
        "═══════════════════════════════════════════════════════════════════════",
        _GENERATED_DEV_KEY,
        _GENERATED_DEV_KEY,
    )

    return _GENERATED_DEV_KEY


def get_generated_dev_key() -> str | None:
    """Return the previously generated dev key without generating a new one."""
    return _GENERATED_DEV_KEY


def clear_generated_dev_key() -> None:
    """Clear the generated dev key (primarily for testing)."""
    global _GENERATED_DEV_KEY
    _GENERATED_DEV_KEY = None


__all__ = [
    "allow_insecure_startup",
    "current_runtime_environment",
    "is_development_environment",
    "generate_ephemeral_dev_key",
    "get_generated_dev_key",
    "clear_generated_dev_key",
]

