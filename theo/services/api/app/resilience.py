"""Compatibility wrapper exposing application resilience facade APIs."""

from __future__ import annotations

from theo.application.facades.resilience import (
    ResilienceError,
    ResilienceMetadata,
    ResiliencePolicy,
    ResilienceSettings,
    create_policy,
    resilient_async_operation,
    resilient_operation,
    set_resilience_policy_factory,
)

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
