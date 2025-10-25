"""Adapter implementing the application resilience policy contract."""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable, MutableMapping, TypeVar

from theo.application.resilience import (
    ResilienceError,
    ResilienceMetadata,
    ResiliencePolicy,
    ResilienceSettings,
)

T = TypeVar("T")


@dataclass(slots=True)
class _CircuitState:
    failures: int = 0
    opened_at: float | None = None
    last_touched: float = 0.0


def _categorise_exception(exc: BaseException) -> str:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, ConnectionError):
        return "provider"
    if isinstance(exc, OSError):
        return "io"
    return "unknown"


class CircuitBreakerResiliencePolicy(ResiliencePolicy):
    """Retry and circuit-breaker implementation used by the API."""

    _circuit_states: MutableMapping[str, _CircuitState] = {}
    _lock = threading.Lock()
    _max_circuit_entries = 512
    _circuit_ttl_seconds = 3600.0

    def __init__(self, settings: ResilienceSettings | None = None) -> None:
        self.settings = settings or ResilienceSettings()
        if self.settings.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

    # ResiliencePolicy interface -------------------------------------------------

    def run(
        self,
        operation: Callable[[], T],
        *,
        key: str,
        classification: str,
    ) -> tuple[T, ResilienceMetadata]:
        start = time.monotonic()
        state = self._check_circuit(key, start)
        attempts = 0
        last_exc: BaseException | None = None
        category = "success"

        for attempts in range(1, self.settings.max_attempts + 1):
            try:
                result = operation()
            except BaseException as exc:
                last_exc = exc
                category = _categorise_exception(exc)
                if attempts >= self.settings.max_attempts:
                    state = self._update_failures(key, time.monotonic())
                    metadata = self._metadata(
                        attempts=attempts,
                        category=category,
                        state=state,
                        last_exception=str(exc),
                        start=start,
                        classification=classification,
                    )
                    raise ResilienceError("Resilient operation failed", metadata) from exc
                continue
            else:
                self._reset_success(key)
                metadata = self._metadata(
                    attempts=attempts,
                    category="success",
                    state=state,
                    last_exception=None,
                    start=start,
                    classification=classification,
                )
                return result, metadata

        assert last_exc is not None  # pragma: no cover - defensive
        raise ResilienceError(
            "Resilient operation failed",
            self._metadata(
                attempts=attempts,
                category=category,
                state=state,
                last_exception=str(last_exc),
                start=start,
                classification=classification,
            ),
        )

    async def run_async(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        key: str,
        classification: str,
    ) -> tuple[T, ResilienceMetadata]:
        start = time.monotonic()
        state = self._check_circuit(key, start)
        attempts = 0
        last_exc: BaseException | None = None
        category = "success"

        for attempts in range(1, self.settings.max_attempts + 1):
            try:
                result = await operation()
            except BaseException as exc:
                last_exc = exc
                category = _categorise_exception(exc)
                if attempts >= self.settings.max_attempts:
                    state = self._update_failures(key, time.monotonic())
                    metadata = self._metadata(
                        attempts=attempts,
                        category=category,
                        state=state,
                        last_exception=str(exc),
                        start=start,
                        classification=classification,
                    )
                    raise ResilienceError("Resilient operation failed", metadata) from exc
                continue
            else:
                self._reset_success(key)
                metadata = self._metadata(
                    attempts=attempts,
                    category="success",
                    state=state,
                    last_exception=None,
                    start=start,
                    classification=classification,
                )
                return result, metadata

        assert last_exc is not None  # pragma: no cover - defensive
        raise ResilienceError(
            "Resilient async operation failed",
            self._metadata(
                attempts=attempts,
                category=category,
                state=state,
                last_exception=str(last_exc),
                start=start,
                classification=classification,
            ),
        )

    # Internal helpers -----------------------------------------------------------

    def _metadata(
        self,
        *,
        attempts: int,
        category: str,
        state: _CircuitState,
        last_exception: str | None,
        start: float,
        classification: str,
    ) -> ResilienceMetadata:
        duration = time.monotonic() - start
        return ResilienceMetadata(
            attempts=attempts,
            category=category,
            circuit_open=state.opened_at is not None,
            last_exception=last_exception,
            duration=duration,
            classification=classification,
            policy=asdict(self.settings),
        )

    def _check_circuit(self, key: str, now: float) -> _CircuitState:
        with self._lock:
            self._prune_circuit_states(now)
            state = self._circuit_states.setdefault(key, _CircuitState())
            self._reset_or_unlock(state, now)
            state.last_touched = now
            if state.opened_at is not None:
                metadata = ResilienceMetadata(
                    attempts=0,
                    category="circuit_open",
                    circuit_open=True,
                    last_exception=None,
                    duration=0.0,
                    classification="circuit",
                    policy=asdict(self.settings),
                )
                raise ResilienceError("Circuit breaker open", metadata)
            return state

    def _update_failures(self, key: str, now: float) -> _CircuitState:
        with self._lock:
            state = self._circuit_states.setdefault(key, _CircuitState())
            state.failures += 1
            state.last_touched = now
            if state.failures >= self.settings.breaker_threshold:
                state.opened_at = now
            return state

    def _reset_success(self, key: str) -> None:
        with self._lock:
            state = self._circuit_states.setdefault(key, _CircuitState())
            state.failures = 0
            state.opened_at = None
            state.last_touched = time.monotonic()

    def _reset_or_unlock(self, state: _CircuitState, now: float) -> None:
        if state.opened_at is None:
            return
        if now - state.opened_at >= self.settings.breaker_reset_seconds:
            state.opened_at = None
            state.failures = 0

    def _prune_circuit_states(self, now: float) -> None:
        states = self._circuit_states
        if len(states) <= self._max_circuit_entries:
            stale_keys = [
                key
                for key, state in states.items()
                if state.last_touched
                and now - state.last_touched >= self._circuit_ttl_seconds
                and state.failures == 0
                and state.opened_at is None
            ]
            for key in stale_keys:
                states.pop(key, None)
            return

        sorted_keys = sorted(states.items(), key=lambda item: item[1].last_touched)
        excess = len(states) - self._max_circuit_entries
        removed = 0
        for key, state in sorted_keys:
            if state.opened_at is None and state.failures == 0:
                states.pop(key, None)
                removed += 1
                if removed >= excess:
                    break


def resilience_policy_factory(settings: ResilienceSettings) -> ResiliencePolicy:
    """Factory compatible with :func:`set_resilience_policy_factory`."""

    return CircuitBreakerResiliencePolicy(settings)


__all__ = ["CircuitBreakerResiliencePolicy", "resilience_policy_factory"]

