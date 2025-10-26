import asyncio
from typing import Awaitable, Callable

import pytest

from theo.application.facades import resilience as resilience_facade
from theo.application.resilience import ResilienceMetadata, ResiliencePolicy, ResilienceSettings


class _Policy(ResiliencePolicy):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def run(
        self,
        operation: Callable[[], object],
        *,
        key: str,
        classification: str,
    ) -> tuple[object, ResilienceMetadata]:
        self.calls.append(("sync", key))
        result = operation()
        return result, ResilienceMetadata(
            attempts=2,
            category=key,
            circuit_open=False,
            last_exception=None,
            duration=0.1,
            classification=classification,
            policy={"name": "custom"},
        )

    async def run_async(
        self,
        operation: Callable[[], Awaitable[object]],
        *,
        key: str,
        classification: str,
    ) -> tuple[object, ResilienceMetadata]:
        self.calls.append(("async", key))
        result = await operation()
        return result, ResilienceMetadata(
            attempts=2,
            category=key,
            circuit_open=False,
            last_exception=None,
            duration=0.1,
            classification=classification,
            policy={"name": "custom"},
        )


@pytest.fixture(autouse=True)
def _reset_factory() -> None:
    previous = getattr(resilience_facade, "_factory", None)
    resilience_facade._factory = None  # type: ignore[attr-defined]
    try:
        yield
    finally:
        resilience_facade._factory = previous  # type: ignore[attr-defined]


def test_create_policy_uses_registered_factory() -> None:
    policy = _Policy()

    def factory(settings: ResilienceSettings) -> ResiliencePolicy:
        assert settings.max_attempts == 5
        return policy

    resilience_facade.set_resilience_policy_factory(factory)

    created = resilience_facade.create_policy(ResilienceSettings(max_attempts=5))

    assert created is policy


def test_resilient_operation_with_default_policy() -> None:
    result, metadata = resilience_facade.resilient_operation(
        lambda: "ok", key="ingest", classification="transient"
    )

    assert result == "ok"
    assert metadata.policy["name"] == "noop"
    assert metadata.attempts == 1


@pytest.mark.asyncio
async def test_resilient_async_operation_uses_policy() -> None:
    policy = _Policy()
    resilience_facade.set_resilience_policy_factory(lambda settings: policy)

    async def runner() -> str:
        await asyncio.sleep(0)
        return "async-ok"

    result, metadata = await resilience_facade.resilient_async_operation(
        runner, key="sync", classification="transient"
    )

    assert result == "async-ok"
    assert metadata.policy["name"] == "custom"
    assert policy.calls[-1] == ("async", "sync")
