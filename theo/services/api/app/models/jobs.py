"""Job schema definitions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeAlias

from pydantic import Field, field_validator

if TYPE_CHECKING:

    class APIModel:
        """Typed placeholder for the runtime Pydantic model base."""

        model_config: object

        def __init__(self, **data: Any) -> None: ...

else:  # pragma: no cover - used only at runtime
    from .base import APIModel


try:  # pragma: no cover - Python 3.12+
    from typing import TypeAliasType
except ImportError:  # pragma: no cover - fallback for older typing
    from typing_extensions import TypeAliasType

JSONScalar = str | int | float | bool | None
JSONValue = TypeAliasType(
    "JSONValue",
    JSONScalar | list["JSONValue"] | dict[str, "JSONValue"],
)
JSONDict: TypeAlias = dict[str, JSONValue]


def _ensure_json_dict(value: Any) -> JSONDict:
    if not isinstance(value, dict):
        msg = "Expected a JSON object with string keys"
        raise TypeError(msg)
    normalized: JSONDict = {}
    for key, item in value.items():
        if not isinstance(key, str):
            msg = "JSON object keys must be strings"
            raise TypeError(msg)
        normalized[key] = _ensure_json_value(item)
    return normalized


def _ensure_json_value(value: Any) -> JSONValue:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_ensure_json_value(item) for item in value]
    if isinstance(value, dict):
        return _ensure_json_dict(value)
    msg = "Value must be JSON serializable"
    raise TypeError(msg)


class JobStatus(APIModel):
    id: str
    document_id: str | None = None
    job_type: str
    status: str
    task_id: str | None = None
    error: str | None = None
    payload: JSONDict | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("payload", mode="before")
    @classmethod
    def _validate_payload(cls, value: Any) -> JSONDict | None:
        if value is None:
            return None
        return _ensure_json_dict(value)


class JobListResponse(APIModel):
    jobs: list[JobStatus]


class JobQueuedResponse(APIModel):
    document_id: str
    status: str


class JobUpdateRequest(APIModel):
    status: str | None = None
    error: str | None = None
    document_id: str | None = None
    task_id: str | None = None
    payload: JSONDict | None = Field(default=None)

    @field_validator("payload", mode="before")
    @classmethod
    def _validate_payload(cls, value: Any) -> JSONDict | None:
        if value is None:
            return None
        return _ensure_json_dict(value)


class JobEnqueueRequest(APIModel):
    task: str
    args: JSONDict | None = Field(default_factory=dict)
    schedule_at: datetime | None = None

    @field_validator("task")
    @classmethod
    def _validate_task(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "Task name must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("args", mode="before")
    @classmethod
    def _validate_args(cls, value: Any) -> JSONDict | None:
        if value is None:
            return None
        return _ensure_json_dict(value)


class JobEnqueueResponse(APIModel):
    job_id: str
    task: str
    args_hash: str
    queued_at: datetime
    schedule_at: datetime | None = None
    status_url: str


class SummaryJobRequest(APIModel):
    document_id: str


class TopicDigestJobRequest(APIModel):
    since: datetime | None = None
    notify: list[str] | None = None

    @field_validator("notify", mode="before")
    @classmethod
    def _validate_notify(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            msg = "Notify must be provided as a list"
            raise TypeError(msg)
        normalized: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                msg = "Notify entries must be strings"
                raise TypeError(msg)
            stripped = entry.strip()
            if stripped:
                normalized.append(stripped)
        return normalized or None


class HNSWRefreshJobRequest(APIModel):
    sample_queries: int = Field(default=25, ge=1, le=500)
    top_k: int = Field(default=10, ge=1, le=200)
