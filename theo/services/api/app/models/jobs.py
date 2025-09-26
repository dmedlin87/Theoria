"""Job schema definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .base import APIModel


class JobStatus(APIModel):
    id: str
    document_id: str | None = None
    job_type: str
    status: str
    task_id: str | None = None
    error: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


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
    payload: dict[str, Any] | None = Field(default=None)


class JobEnqueueRequest(APIModel):
    task: str
    args: dict[str, Any] | None = Field(default_factory=dict)
    schedule_at: datetime | None = None


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
