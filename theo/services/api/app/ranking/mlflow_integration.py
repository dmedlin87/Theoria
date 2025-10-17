"""Helpers for resolving reranker checkpoints from MLflow."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class MlflowResolutionError(RuntimeError):
    """Raised when MLflow artifacts cannot be resolved."""


def _normalise_scheme(model_uri: str, scheme: str) -> Optional[str]:
    if model_uri.startswith(scheme):
        return model_uri[len(scheme) :]
    return None


def _strip_models_prefix(model_uri: str) -> Optional[str]:
    remainder = _normalise_scheme(model_uri, "models://")
    if remainder is not None:
        return remainder
    return _normalise_scheme(model_uri, "models:/")


def _strip_runs_prefix(model_uri: str) -> Optional[str]:
    remainder = _normalise_scheme(model_uri, "runs://")
    if remainder is not None:
        return remainder
    return _normalise_scheme(model_uri, "runs:/")


def is_mlflow_uri(reference: str | Path | None) -> bool:
    """Return ``True`` if the reference looks like an MLflow URI."""

    if reference is None:
        return False
    text = str(reference)
    return _strip_models_prefix(text) is not None or _strip_runs_prefix(text) is not None


@dataclass
class _ModelsUri:
    name: str
    target_type: str
    target: str
    artifact_path: str


def _parse_models_uri(model_uri: str) -> Optional[_ModelsUri]:
    remainder = _strip_models_prefix(model_uri)
    if remainder is None:
        return None

    if "@" in remainder:
        name, alias_payload = remainder.split("@", 1)
        if not name:
            return None
        if "/" in alias_payload:
            alias, artifact_path = alias_payload.split("/", 1)
        else:
            alias, artifact_path = alias_payload, ""
        alias = alias.strip()
        if not alias:
            return None
        return _ModelsUri(name=name, target_type="alias", target=alias, artifact_path=artifact_path)

    parts = remainder.split("/", 2)
    if len(parts) < 2:
        return None
    name, segment = parts[0], parts[1]
    artifact_path = parts[2] if len(parts) > 2 else ""
    if segment.isdigit():
        return _ModelsUri(name=name, target_type="version", target=segment, artifact_path=artifact_path)
    return _ModelsUri(name=name, target_type="stage", target=segment, artifact_path=artifact_path)


@dataclass
class _RunsUri:
    run_id: str
    artifact_path: str


def _parse_runs_uri(model_uri: str) -> Optional[_RunsUri]:
    remainder = _strip_runs_prefix(model_uri)
    if remainder is None:
        return None
    parts = remainder.split("/", 1)
    run_id = parts[0]
    artifact_path = parts[1] if len(parts) > 1 else ""
    if not run_id:
        return None
    return _RunsUri(run_id=run_id, artifact_path=artifact_path)


def resolve_mlflow_artifact(model_uri: str) -> Path:
    """Download the MLflow artifact for ``model_uri`` and return the local path."""

    try:  # pragma: no cover - exercised in environments without MLflow
        import mlflow
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise MlflowResolutionError("MLflow is required to load registry artifacts") from exc

    local_path = Path(mlflow.artifacts.download_artifacts(artifact_uri=model_uri))
    if local_path.is_dir():
        joblib_candidates = sorted(local_path.rglob("*.joblib"))
        if len(joblib_candidates) == 1:
            return joblib_candidates[0]
        if not joblib_candidates:
            raise MlflowResolutionError(
                f"No joblib artifacts found in MLflow download for '{model_uri}'"
            )
        raise MlflowResolutionError(
            f"Multiple joblib artifacts found in MLflow download for '{model_uri}'"
        )
    return local_path


def mlflow_signature(model_uri: str) -> Optional[tuple[str, str, str]]:
    """Return a signature tuple for the referenced MLflow artifact if possible."""

    try:  # pragma: no cover - exercised in environments without MLflow
        from mlflow.tracking import MlflowClient
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        return None

    client = MlflowClient()

    models_uri = _parse_models_uri(model_uri)
    if models_uri is not None:
        if models_uri.target_type == "version":
            version = client.get_model_version(models_uri.name, models_uri.target)
        elif models_uri.target_type == "alias" and hasattr(client, "get_model_version_by_alias"):
            version = client.get_model_version_by_alias(models_uri.name, models_uri.target)
        else:
            candidates = client.get_latest_versions(models_uri.name, stages=[models_uri.target])
            version = candidates[0] if candidates else None
        if version is None:
            return None
        last_updated = getattr(version, "last_updated_timestamp", None)
        stage = getattr(version, "current_stage", "")
        return (str(version.version), str(last_updated or ""), stage)

    runs_uri = _parse_runs_uri(model_uri)
    if runs_uri is not None:
        run = client.get_run(runs_uri.run_id)
        end_time = getattr(run.info, "end_time", None)
        update_time = getattr(run.info, "update_time", None)
        timestamp = end_time or update_time or 0
        return (run.info.run_id, str(timestamp), runs_uri.artifact_path)

    return None
