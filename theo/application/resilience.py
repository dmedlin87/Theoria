"""Application-level resilience policies and metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@dataclass(slots=True)
class ResilienceSettings:
    """Configuration describing retry and circuit-breaker behaviour."""

    max_attempts: int = 3
    breaker_threshold: int = 5
    breaker_reset_seconds: float = 30.0


@dataclass(slots=True)
class ResilienceMetadata:
    """Structured information about a resilient call attempt."""

    attempts: int
    category: str
    circuit_open: bool
    last_exception: str | None
    duration: float
    classification: str
    policy: Mapping[str, Any]


class ResilienceError(Exception):
    """Raised when a resilient call exhausts all attempts or the circuit is open."""

    def __init__(self, message: str, metadata: ResilienceMetadata) -> None:
        super().__init__(message)
        self.metadata = metadata


@runtime_checkable
class ResiliencePolicy(Protocol):
    """Protocol defining the behaviour for resilient execution."""

    def run(
        self,
        operation: Callable[[], T],
        *,
        key: str,
        classification: str,
    ) -> tuple[T, ResilienceMetadata]:
        """Execute ``operation`` with retry and circuit-breaking semantics."""

    async def run_async(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        key: str,
        classification: str,
    ) -> tuple[T, ResilienceMetadata]:
        """Async variant of :meth:`run`."""


__all__ = [
    "ResilienceError",
    "ResilienceMetadata",
    "ResiliencePolicy",
    "ResilienceSettings",
]

