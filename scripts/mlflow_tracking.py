"""Utility helpers for optional MLflow tracking in CLI scripts."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

MLFLOW_TRACKING_ENV = "THEO_MLFLOW_TRACKING_URI"
MLFLOW_REGISTRY_ENV = "THEO_MLFLOW_REGISTRY_URI"

try:  # pragma: no cover - optional dependency
    import mlflow
except ModuleNotFoundError:  # pragma: no cover - exercised in CI without MLflow
    mlflow = None  # type: ignore[assignment]


def _configure_mlflow() -> None:
    """Apply tracking and registry URIs when MLflow is available."""

    if mlflow is None:
        return
    tracking_uri = os.getenv(MLFLOW_TRACKING_ENV)
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    registry_uri = os.getenv(MLFLOW_REGISTRY_ENV)
    if registry_uri:
        mlflow.set_registry_uri(registry_uri)


@contextmanager
def mlflow_run(run_name: str, *, tags: dict[str, str] | None = None) -> Iterator[object | None]:
    """Start an MLflow run when MLflow is installed."""

    if mlflow is None:
        yield None
        return

    _configure_mlflow()

    active = mlflow.active_run()
    if active is not None:
        yield mlflow
        return

    with mlflow.start_run(run_name=run_name, tags=tags):
        yield mlflow


def mlflow_enabled() -> bool:
    """Return ``True`` when MLflow is installed and importable."""

    return mlflow is not None
