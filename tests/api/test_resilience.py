import asyncio
import itertools

import pytest

from theo.application.facades import resilience as resilience_facade
from theo.application.resilience import ResilienceError, ResilienceSettings
from theo.infrastructure.api.app.adapters import resilience as resilience_adapter


@pytest.fixture(autouse=True)
def _configure_resilience(monkeypatch):
    monkeypatch.setattr(resilience_facade, "_factory", resilience_adapter.resilience_policy_factory)
    resilience_adapter.CircuitBreakerResiliencePolicy._circuit_states.clear()
    yield
    resilience_adapter.CircuitBreakerResiliencePolicy._circuit_states.clear()


def test_resilient_operation_success():
    result, metadata = resilience_facade.resilient_operation(
        lambda: "ok",
        key="resilience-success",
        classification="unit-test",
    )

    assert result == "ok"
    assert metadata.attempts == 1
    assert metadata.category == "success"
    assert metadata.classification == "unit-test"
    assert metadata.circuit_open is False
    assert metadata.policy["max_attempts"] == ResilienceSettings().max_attempts


def test_resilient_operation_retries_then_succeeds():
    call_count = {"value": 0}

    def flaky_operation() -> str:
        call_count["value"] += 1
        if call_count["value"] < 3:
            raise ConnectionError("temporary")
        return "stable"

    policy = resilience_adapter.CircuitBreakerResiliencePolicy(
        ResilienceSettings(max_attempts=3, breaker_threshold=5)
    )

    result, metadata = resilience_facade.resilient_operation(
        flaky_operation,
        key="resilience-retry",
        classification="unit-test",
        policy=policy,
    )

    assert result == "stable"
    assert call_count["value"] == 3
    assert metadata.attempts == 3
    assert metadata.category == "success"

    state = resilience_adapter.CircuitBreakerResiliencePolicy._circuit_states["resilience-retry"]
    assert state.failures == 0
    assert state.opened_at is None


def test_resilient_operation_connection_error_classification():
    policy = resilience_adapter.CircuitBreakerResiliencePolicy(
        ResilienceSettings(max_attempts=2, breaker_threshold=5)
    )

    def failing_operation() -> str:
        raise ConnectionError("provider failure")

    with pytest.raises(ResilienceError) as error:
        resilience_facade.resilient_operation(
            failing_operation,
            key="resilience-provider-category",
            classification="unit-test",
            policy=policy,
        )

    metadata = error.value.metadata
    assert metadata.category == "provider"
    assert metadata.classification == "unit-test"


def test_resilient_operation_circuit_breaker(monkeypatch):
    policy = resilience_adapter.CircuitBreakerResiliencePolicy(
        ResilienceSettings(max_attempts=2, breaker_threshold=1, breaker_reset_seconds=60)
    )

    time_values = itertools.count(start=100, step=1)
    monkeypatch.setattr(resilience_adapter.time, "monotonic", lambda: next(time_values))

    def always_timeout() -> str:
        raise TimeoutError("network timeout")

    with pytest.raises(ResilienceError) as error:
        resilience_facade.resilient_operation(
            always_timeout,
            key="resilience-breaker",
            classification="unit-test",
            policy=policy,
        )

    metadata = error.value.metadata
    assert metadata.category == "timeout"
    assert metadata.attempts == policy.settings.max_attempts
    assert metadata.circuit_open is True

    with pytest.raises(ResilienceError) as circuit_error:
        resilience_facade.resilient_operation(
            lambda: "should not execute",
            key="resilience-breaker",
            classification="unit-test",
            policy=policy,
        )

    assert circuit_error.value.metadata.category == "circuit_open"
    assert circuit_error.value.metadata.circuit_open is True
    assert circuit_error.value.metadata.attempts == 0


def test_resilient_operation_requires_positive_attempts():
    with pytest.raises(ValueError):
        resilience_adapter.CircuitBreakerResiliencePolicy(
            ResilienceSettings(max_attempts=0)
        )


def test_resilient_async_operation_success():
    async def operation() -> str:
        return "async-ok"

    result, metadata = asyncio.run(
        resilience_facade.resilient_async_operation(
            operation,
            key="resilience-async",
            classification="unit-test",
        )
    )

    assert result == "async-ok"
    assert metadata.attempts == 1
    assert metadata.category == "success"
    assert metadata.circuit_open is False


def test_resilient_async_operation_failure():
    policy = resilience_adapter.CircuitBreakerResiliencePolicy(
        ResilienceSettings(max_attempts=2, breaker_threshold=2)
    )
    attempts = {"count": 0}

    async def failing_operation() -> str:
        attempts["count"] += 1
        raise OSError("disk error")

    with pytest.raises(ResilienceError) as error:
        asyncio.run(
            resilience_facade.resilient_async_operation(
                failing_operation,
                key="resilience-async-failure",
                classification="unit-test",
                policy=policy,
            )
        )

    metadata = error.value.metadata
    assert attempts["count"] == policy.settings.max_attempts
    assert metadata.attempts == policy.settings.max_attempts
    assert metadata.category == "io"
    assert metadata.circuit_open is False
