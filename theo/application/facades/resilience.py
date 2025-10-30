"""Facade for resilience policy execution."""

from __future__ import annotations

import time
from typing import Awaitable, Callable, Optional, TypeVar

from ..resilience import ResilienceError, ResilienceMetadata, ResiliencePolicy, ResilienceSettings

T = TypeVar("T")

_factory: Callable[[ResilienceSettings], ResiliencePolicy] | None = None


def set_resilience_policy_factory(factory: Callable[[ResilienceSettings], ResiliencePolicy]) -> None:
    """Register the factory used to construct resilience policies."""

    global _factory
    _factory = factory


class _NoOpResiliencePolicy:
    """Fallback policy that executes operations without retries."""

    def __init__(self, settings: ResilienceSettings) -> None:
        self._settings = settings

    def run(
        self,
        operation: Callable[[], T],
        *,
        key: str,
        classification: str,
    ) -> tuple[T, ResilienceMetadata]:
        start_time = time.perf_counter()
        result = operation()
        duration = time.perf_counter() - start_time
        metadata = ResilienceMetadata(
            attempts=1,
            category=key,
            circuit_open=False,
            last_exception=None,
            duration=max(duration, 0.0),
            classification=classification,
            policy={"name": "noop"},
        )
        return result, metadata

    async def run_async(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        key: str,
        classification: str,
    ) -> tuple[T, ResilienceMetadata]:
        start_time = time.perf_counter()
        result = await operation()
        duration = time.perf_counter() - start_time
        metadata = ResilienceMetadata(
            attempts=1,
            category=key,
            circuit_open=False,
            last_exception=None,
            duration=max(duration, 0.0),
            classification=classification,
            policy={"name": "noop"},
        )
        return result, metadata


def create_policy(settings: Optional[ResilienceSettings] = None) -> ResiliencePolicy:
    """Create a resilience policy using the registered factory."""

    active_settings = settings or ResilienceSettings()
    if _factory is None:
        return _NoOpResiliencePolicy(active_settings)
    return _factory(active_settings)


def resilient_operation(
    operation: Callable[[], T],
    *,
    key: str,
    classification: str,
    policy: Optional[ResiliencePolicy] = None,
    settings: Optional[ResilienceSettings] = None,
) -> tuple[T, ResilienceMetadata]:
    """Execute ``operation`` via the configured resilience policy."""

    active_policy = policy or create_policy(settings)
    return active_policy.run(operation, key=key, classification=classification)


async def resilient_async_operation(
    operation: Callable[[], Awaitable[T]],
    *,
    key: str,
    classification: str,
    policy: Optional[ResiliencePolicy] = None,
    settings: Optional[ResilienceSettings] = None,
) -> tuple[T, ResilienceMetadata]:
    """Async variant of :func:`resilient_operation`."""

    active_policy = policy or create_policy(settings)
    return await active_policy.run_async(operation, key=key, classification=classification)


__all__ = [
    "ResilienceError",
    "ResilienceMetadata",
    "ResiliencePolicy",
    "ResilienceSettings",
    "create_policy",
    "resilient_async_operation",
    "resilient_operation",
    "set_resilience_policy_factory",
]

