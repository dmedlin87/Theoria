import pytest

from theo.application.resilience import (
    ResilienceError,
    ResilienceMetadata,
    ResiliencePolicy,
    ResilienceSettings,
)


def test_resilience_settings_defaults() -> None:
    settings = ResilienceSettings()

    assert settings.max_attempts == 3
    assert settings.breaker_threshold == 5
    assert settings.breaker_reset_seconds == 30.0


def test_resilience_error_wraps_metadata() -> None:
    metadata = ResilienceMetadata(
        attempts=2,
        category="ingest",
        circuit_open=False,
        last_exception="ValueError",
        duration=0.5,
        classification="transient",
        policy={"name": "retry"},
    )

    error = ResilienceError("operation failed", metadata)

    assert error.metadata is metadata
    assert "operation failed" in str(error)


class _PolicyImpl:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[str] = []

    def run(self, operation, *, key: str, classification: str):
        self.calls.append(f"sync:{key}:{classification}")
        return self.result, ResilienceMetadata(
            attempts=1,
            category=key,
            circuit_open=False,
            last_exception=None,
            duration=0.0,
            classification=classification,
            policy={"name": "custom"},
        )

    async def run_async(self, operation, *, key: str, classification: str):
        self.calls.append(f"async:{key}:{classification}")
        return self.result, ResilienceMetadata(
            attempts=1,
            category=key,
            circuit_open=False,
            last_exception=None,
            duration=0.0,
            classification=classification,
            policy={"name": "custom"},
        )


def test_resilience_policy_runtime_check() -> None:
    policy = _PolicyImpl(result="ok")

    assert isinstance(policy, ResiliencePolicy)
