"""Runtime feature flags for Theo Engine startup behaviours."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

LOGGER = logging.getLogger(__name__)

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


__all__ = ["allow_insecure_startup", "current_runtime_environment"]

