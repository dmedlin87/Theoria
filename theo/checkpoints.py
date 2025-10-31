from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


CURRENT_EMBEDDING_CHECKPOINT_VERSION = 2


class CheckpointValidationError(ValueError):
    """Raised when a checkpoint payload cannot be validated."""


def _coerce_int(field: str, value: Any) -> int:
    if isinstance(value, bool):
        raise CheckpointValidationError(f"{field} must be an integer")
    if value is None:
        raise CheckpointValidationError(f"{field} is required")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise CheckpointValidationError(f"{field} must be an integer") from exc
    if result < 0:
        raise CheckpointValidationError(f"{field} must be non-negative")
    return result


def _coerce_optional_str(field: str, value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        if value == "":
            return None
        return value
    raise CheckpointValidationError(f"{field} must be a string or null")


def _parse_datetime(field: str, value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError as exc:
            raise CheckpointValidationError(f"{field} must be an ISO timestamp") from exc
    else:
        raise CheckpointValidationError(f"{field} must be an ISO timestamp")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


@dataclass(slots=True)
class EmbeddingRebuildCheckpoint:
    """Typed representation of the embedding rebuild checkpoint payload."""

    version: int
    processed: int
    total: int
    last_id: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.version != CURRENT_EMBEDDING_CHECKPOINT_VERSION:
            raise CheckpointValidationError(
                f"Unsupported checkpoint version: {self.version}"
            )
        if self.processed < 0:
            raise CheckpointValidationError("processed must be non-negative")
        if self.total < 0:
            raise CheckpointValidationError("total must be non-negative")
        if self.processed > self.total:
            raise CheckpointValidationError("processed cannot exceed total")
        if self.last_id is not None and not isinstance(self.last_id, str):
            raise CheckpointValidationError("last_id must be a string or null")

        if not isinstance(self.metadata, dict):
            raise CheckpointValidationError("metadata must be a mapping")
        for key in self.metadata.keys():
            if not isinstance(key, str):
                raise CheckpointValidationError("metadata keys must be strings")

        for field_name in ("created_at", "updated_at"):
            value = getattr(self, field_name)
            if not isinstance(value, datetime):
                raise CheckpointValidationError(
                    f"{field_name} must be a datetime instance"
                )
            if value.tzinfo is None:
                object.__setattr__(
                    self, field_name, value.replace(tzinfo=timezone.utc)
                )
            else:
                object.__setattr__(
                    self, field_name, value.astimezone(timezone.utc)
                )

        if self.updated_at < self.created_at:
            raise CheckpointValidationError(
                "updated_at cannot be earlier than created_at"
            )

    @classmethod
    def build(
        cls,
        *,
        processed: int,
        total: int,
        last_id: str | None,
        metadata: Mapping[str, Any] | None,
        previous: "EmbeddingRebuildCheckpoint" | None = None,
    ) -> "EmbeddingRebuildCheckpoint":
        now = datetime.now(timezone.utc)
        created_at = previous.created_at if previous else now
        payload_metadata = dict(metadata or {})
        return cls(
            version=CURRENT_EMBEDDING_CHECKPOINT_VERSION,
            processed=processed,
            total=total,
            last_id=last_id,
            metadata=payload_metadata,
            created_at=created_at,
            updated_at=now,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "processed": self.processed,
            "total": self.total,
            "last_id": self.last_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


def _migrate_v1_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    processed = data.get("processed", 0)
    total = data.get("total", processed)
    last_id = data.get("last_id")
    metadata = data.get("metadata") or {}
    updated_at_raw = data.get("updated_at")
    created_at_raw = data.get("created_at") or updated_at_raw

    now = datetime.now(timezone.utc)
    if updated_at_raw is None:
        updated_at = now
    else:
        updated_at = _parse_datetime("updated_at", updated_at_raw)
    if created_at_raw is None:
        created_at = updated_at
    else:
        created_at = _parse_datetime("created_at", created_at_raw)

    return {
        "version": CURRENT_EMBEDDING_CHECKPOINT_VERSION,
        "processed": processed,
        "total": total,
        "last_id": last_id,
        "metadata": metadata,
        "created_at": created_at.isoformat(),
        "updated_at": updated_at.isoformat(),
    }


def deserialize_embedding_rebuild_checkpoint(
    payload: Mapping[str, Any]
) -> EmbeddingRebuildCheckpoint:
    data = dict(payload)
    version_value = data.get("version")
    if version_value is None:
        data = _migrate_v1_payload(data)
        version_value = CURRENT_EMBEDDING_CHECKPOINT_VERSION
    else:
        try:
            version_value = int(version_value)
        except (TypeError, ValueError) as exc:
            raise CheckpointValidationError("version must be an integer") from exc
        if version_value == 1:
            data = _migrate_v1_payload(data)
            version_value = CURRENT_EMBEDDING_CHECKPOINT_VERSION
        elif version_value != CURRENT_EMBEDDING_CHECKPOINT_VERSION:
            raise CheckpointValidationError(
                f"Unsupported checkpoint version: {version_value}"
            )

    processed = _coerce_int("processed", data.get("processed"))
    total = _coerce_int("total", data.get("total"))
    if processed > total:
        raise CheckpointValidationError("processed cannot exceed total")
    last_id = _coerce_optional_str("last_id", data.get("last_id"))

    metadata = data.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        raise CheckpointValidationError("metadata must be a mapping")
    metadata_dict = dict(metadata)
    for key in metadata_dict:
        if not isinstance(key, str):
            raise CheckpointValidationError("metadata keys must be strings")

    created_at = _parse_datetime("created_at", data.get("created_at"))
    updated_at = _parse_datetime("updated_at", data.get("updated_at"))

    return EmbeddingRebuildCheckpoint(
        version=CURRENT_EMBEDDING_CHECKPOINT_VERSION,
        processed=processed,
        total=total,
        last_id=last_id,
        metadata=metadata_dict,
        created_at=created_at,
        updated_at=updated_at,
    )


def serialize_embedding_rebuild_checkpoint(
    checkpoint: EmbeddingRebuildCheckpoint,
) -> dict[str, Any]:
    return checkpoint.to_dict()


import logging

_LOGGER = logging.getLogger(__name__)


def load_embedding_rebuild_checkpoint(
    path: Path, *, strict: bool = False
) -> EmbeddingRebuildCheckpoint | None:
    """Load embedding rebuild checkpoint from file.
    
    Args:
        path: Path to the checkpoint file
        strict: If True, raises exceptions on invalid payloads instead of returning None
        
    Returns:
        The checkpoint object if valid, None if missing or invalid (when strict=False)
        
    Raises:
        CheckpointValidationError: When strict=True and checkpoint is invalid
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        if strict:
            raise CheckpointValidationError(f"Invalid JSON in checkpoint {path}: {exc}") from exc
        _LOGGER.warning("Invalid JSON in checkpoint %s: %s", path, exc)
        return None
        
    if not isinstance(payload, Mapping):
        error_msg = f"Invalid payload type in checkpoint {path}: expected mapping, got {type(payload)}"
        if strict:
            raise CheckpointValidationError(error_msg)
        _LOGGER.warning(error_msg)
        return None

    try:
        return deserialize_embedding_rebuild_checkpoint(payload)
    except CheckpointValidationError as exc:
        if strict:
            raise
        _LOGGER.warning("Invalid checkpoint %s: %s", path, exc)
        return None


def save_embedding_rebuild_checkpoint(
    path: Path, checkpoint: EmbeddingRebuildCheckpoint
) -> None:
    """Atomically save embedding rebuild checkpoint to file.
    
    Uses atomic write via temporary file to prevent corruption on crash/interruption.
    
    Args:
        path: Target path for the checkpoint file
        checkpoint: Checkpoint data to save
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = serialize_embedding_rebuild_checkpoint(checkpoint)
    json_content = json.dumps(payload, indent=2)
    
    # Atomic write: write to temporary file, fsync, then rename
    with tempfile.NamedTemporaryFile(
        mode='w', 
        delete=False, 
        dir=path.parent, 
        encoding='utf-8',
        prefix=f".{path.name}.",
        suffix='.tmp'
    ) as tmp_file:
        tmp_file.write(json_content)
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        tmp_path = Path(tmp_file.name)
    
    try:
        # Atomic rename to final location
        tmp_path.replace(path)
    except Exception:
        # Clean up temporary file on failure
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass  # Best effort cleanup
        raise
