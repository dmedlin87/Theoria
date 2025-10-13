"""Utilities for resilient execution of external I/O operations."""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable, Mapping, MutableMapping, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class ResiliencePolicy:
    """Configuration for retry and circuit-breaking behaviour."""

    max_attempts: int = 3
    breaker_threshold: int = 5
    breaker_reset_seconds: float = 30.0


@dataclass(slots=True)
class CircuitState:
    failures: int = 0
    opened_at: float | None = None


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

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["policy"] = dict(self.policy)
        return data


class ResilienceError(Exception):
    """Raised when a resilient call exhausts all attempts or the circuit is open."""

    def __init__(self, message: str, metadata: ResilienceMetadata) -> None:
        super().__init__(message)
        self.metadata = metadata


_CIRCUIT_STATES: MutableMapping[str, CircuitState] = {}
_LOCK = threading.Lock()


def _categorise_exception(exc: BaseException) -> str:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, ConnectionError):
        return "provider"
    if isinstance(exc, OSError):
        return "io"
    return "unknown"


def _reset_or_unlock(key: str, policy: ResiliencePolicy, now: float) -> None:
    state = _CIRCUIT_STATES.setdefault(key, CircuitState())
    if state.opened_at is None:
        return
    if now - state.opened_at >= policy.breaker_reset_seconds:
        state.opened_at = None
        state.failures = 0


def _check_circuit(key: str, policy: ResiliencePolicy, now: float) -> CircuitState:
    with _LOCK:
        state = _CIRCUIT_STATES.setdefault(key, CircuitState())
        _reset_or_unlock(key, policy, now)
        if state.opened_at is not None:
            metadata = ResilienceMetadata(
                attempts=0,
                category="circuit_open",
                circuit_open=True,
                last_exception=None,
                duration=0.0,
                classification="circuit",
                policy=asdict(policy),
            )
            raise ResilienceError("Circuit breaker open", metadata)
        return state


def _update_failures(key: str, policy: ResiliencePolicy, now: float) -> CircuitState:
    with _LOCK:
        state = _CIRCUIT_STATES.setdefault(key, CircuitState())
        state.failures += 1
        if state.failures >= policy.breaker_threshold:
            state.opened_at = now
        return state


def _reset_success(key: str) -> None:
    with _LOCK:
        state = _CIRCUIT_STATES.setdefault(key, CircuitState())
        state.failures = 0
        state.opened_at = None


def resilient_operation(
    operation: Callable[[], T],
    *,
    key: str,
    classification: str,
    policy: ResiliencePolicy | None = None,
) -> tuple[T, ResilienceMetadata]:
    """Execute ``operation`` with retries and circuit-breaking."""

    policy = policy or ResiliencePolicy()
    if policy.max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    start = time.monotonic()
    state = _check_circuit(key, policy, start)
    attempts = 0
    last_exc: BaseException | None = None
    category = "success"

    for attempts in range(1, policy.max_attempts + 1):
        try:
            result = operation()
        except BaseException as exc:  # pragma: no cover - exercised via tests
            last_exc = exc
            category = _categorise_exception(exc)
            if attempts >= policy.max_attempts:
                state = _update_failures(key, policy, time.monotonic())
                metadata = ResilienceMetadata(
                    attempts=attempts,
                    category=category,
                    circuit_open=state.opened_at is not None,
                    last_exception=str(exc),
                    duration=time.monotonic() - start,
                    classification=classification,
                    policy=asdict(policy),
                )
                raise ResilienceError("Resilient operation failed", metadata) from exc
            continue
        else:
            _reset_success(key)
            metadata = ResilienceMetadata(
                attempts=attempts,
                category="success",
                circuit_open=False,
                last_exception=None,
                duration=time.monotonic() - start,
                classification=classification,
                policy=asdict(policy),
            )
            return result, metadata

    assert last_exc is not None  # pragma: no cover
    raise ResilienceError(  # pragma: no cover
        "Resilient operation failed",
        ResilienceMetadata(
            attempts=attempts,
            category=category,
            circuit_open=state.opened_at is not None,
            last_exception=str(last_exc),
            duration=time.monotonic() - start,
            classification=classification,
            policy=asdict(policy),
        ),
    )


async def resilient_async_operation(
    operation: Callable[[], Awaitable[T]],
    *,
    key: str,
    classification: str,
    policy: ResiliencePolicy | None = None,
) -> tuple[T, ResilienceMetadata]:
    """Async variant of :func:`resilient_operation`."""

    policy = policy or ResiliencePolicy()
    if policy.max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    start = time.monotonic()
    state = _check_circuit(key, policy, start)
    attempts = 0
    last_exc: BaseException | None = None
    category = "success"

    for attempts in range(1, policy.max_attempts + 1):
        try:
            result = await operation()
        except BaseException as exc:  # pragma: no cover - exercised via tests
            last_exc = exc
            category = _categorise_exception(exc)
            if attempts >= policy.max_attempts:
                state = _update_failures(key, policy, time.monotonic())
                metadata = ResilienceMetadata(
                    attempts=attempts,
                    category=category,
                    circuit_open=state.opened_at is not None,
                    last_exception=str(exc),
                    duration=time.monotonic() - start,
                    classification=classification,
                    policy=asdict(policy),
                )
                raise ResilienceError("Resilient operation failed", metadata) from exc
            continue
        else:
            _reset_success(key)
            metadata = ResilienceMetadata(
                attempts=attempts,
                category="success",
                circuit_open=False,
                last_exception=None,
                duration=time.monotonic() - start,
                classification=classification,
                policy=asdict(policy),
            )
            return result, metadata

    assert last_exc is not None  # pragma: no cover
    raise ResilienceError(  # pragma: no cover
        "Resilient async operation failed",
        ResilienceMetadata(
            attempts=attempts,
            category=category,
            circuit_open=state.opened_at is not None,
            last_exception=str(last_exc),
            duration=time.monotonic() - start,
            classification=classification,
            policy=asdict(policy),
        ),
    )


__all__ = [
    "ResilienceError",
    "ResilienceMetadata",
    "ResiliencePolicy",
    "resilient_operation",
    "resilient_async_operation",
]

