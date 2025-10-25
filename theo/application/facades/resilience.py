"""Facade for resilience policy execution."""

from __future__ import annotations

from typing import Awaitable, Callable, Optional, TypeVar

from ..resilience import ResilienceError, ResilienceMetadata, ResiliencePolicy, ResilienceSettings

T = TypeVar("T")

_factory: Callable[[ResilienceSettings], ResiliencePolicy] | None = None


def set_resilience_policy_factory(factory: Callable[[ResilienceSettings], ResiliencePolicy]) -> None:
    """Register the factory used to construct resilience policies."""

    global _factory
    _factory = factory


def _ensure_factory() -> Callable[[ResilienceSettings], ResiliencePolicy]:
    if _factory is None:
        raise RuntimeError("Resilience policy factory has not been configured")
    return _factory


def create_policy(settings: Optional[ResilienceSettings] = None) -> ResiliencePolicy:
    """Create a resilience policy using the registered factory."""

    factory = _ensure_factory()
    return factory(settings or ResilienceSettings())


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

