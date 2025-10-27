"""Shared runtime guards used during API application startup."""

from __future__ import annotations

import logging
import os
from typing import Callable, Protocol


class _AllowInsecureStartup(Protocol):
    def __call__(self) -> bool:  # pragma: no cover - protocol definition
        ...


class _GetEnvironmentLabel(Protocol):
    def __call__(self) -> str:  # pragma: no cover - protocol definition
        ...


class _ConsoleTracer(Protocol):
    def __call__(self) -> None:  # pragma: no cover - protocol definition
        ...


class _GetSecret(Protocol):
    def __call__(self) -> str | None:  # pragma: no cover - protocol definition
        ...


def should_enable_console_traces(env_get: Callable[[str, str], str] = os.getenv) -> bool:
    """Return ``True`` when console traces should be enabled."""

    value = env_get("THEO_ENABLE_CONSOLE_TRACES", "0").lower()
    return value in {"1", "true", "yes"}


def configure_console_traces(
    settings: object,
    *,
    console_tracer: _ConsoleTracer,
    should_enable: Callable[[], bool],
) -> None:
    """Invoke the console tracer when the runtime flag is enabled."""

    del settings  # Reserved for future conditional configuration
    if should_enable():
        console_tracer()


def enforce_authentication_requirements(
    settings: object,
    *,
    allow_insecure_startup: _AllowInsecureStartup,
    get_environment_label: _GetEnvironmentLabel,
    logger: logging.Logger,
) -> None:
    """Validate the authentication configuration prior to boot."""

    insecure_ok = allow_insecure_startup()
    auth_allow_anonymous = getattr(settings, "auth_allow_anonymous", False)
    api_keys = getattr(settings, "api_keys", [])
    has_jwt = getattr(settings, "has_auth_jwt_credentials", lambda: False)
    environment = (get_environment_label() or "").strip().lower() or "production"
    allows_anonymous = environment in {"development", "dev", "local", "test", "testing"}

    if auth_allow_anonymous and not allows_anonymous:
        message = (
            "THEO_AUTH_ALLOW_ANONYMOUS is disabled for the current environment "
            f"({environment}). Remove the override or switch to a development "
            "profile before starting the service."
        )
        logger.critical(message)
        raise RuntimeError(message)

    if auth_allow_anonymous and not insecure_ok:
        message = (
            "THEO_AUTH_ALLOW_ANONYMOUS requires THEO_ALLOW_INSECURE_STARTUP for local"
            " testing. Disable anonymous access or set THEO_ALLOW_INSECURE_STARTUP"
            "=1."
        )
        logger.critical(message)
        raise RuntimeError(message)

    if api_keys or has_jwt():
        return

    if insecure_ok:
        logger.warning(
            "Starting without API credentials because THEO_ALLOW_INSECURE_STARTUP is"
            " enabled. Do not use this configuration outside isolated development"
            " environments."
        )
        return

    message = (
        "API authentication is not configured. Set THEO_API_KEYS or JWT settings"
        " before starting the service, or enable THEO_ALLOW_INSECURE_STARTUP=1 for"
        " local testing."
    )
    logger.critical(message)
    raise RuntimeError(message)


def enforce_secret_requirements(
    get_settings_secret: _GetSecret,
    *,
    allow_insecure_startup: _AllowInsecureStartup,
    logger: logging.Logger,
) -> None:
    """Ensure the SETTINGS_SECRET_KEY prerequisite has been met."""

    if get_settings_secret():
        return

    if allow_insecure_startup():
        logger.warning(
            "Starting without SETTINGS_SECRET_KEY because THEO_ALLOW_INSECURE_STARTUP"
            " is enabled. Secrets will not be persisted securely."
        )
        return

    message = (
        "SETTINGS_SECRET_KEY must be configured before starting the service. Set the"
        " environment variable and restart the service or enable"
        " THEO_ALLOW_INSECURE_STARTUP=1 for local development."
    )
    logger.error(message)
    raise RuntimeError(message)


__all__ = [
    "configure_console_traces",
    "enforce_authentication_requirements",
    "enforce_secret_requirements",
    "should_enable_console_traces",
]

