"""Pydantic schemas for research trail APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .base import APIModel


class TrailSource(APIModel):
    id: str
    trail_id: str
    source_type: str
    reference: str
    meta: Any | None = None
    created_at: datetime
    updated_at: datetime


class AgentStep(APIModel):
    id: str
    trail_id: str
    step_index: int
    tool: str
    action: str | None = None
    status: str
    input_payload: Any | None = None
    output_payload: Any | None = None
    output_digest: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class AgentTrail(APIModel):
    id: str
    workflow: str
    mode: str | None = None
    user_id: str | None = None
    status: str
    plan_md: str | None = None
    final_md: str | None = None
    input_payload: Any | None = None
    output_payload: Any | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    last_replayed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    steps: list[AgentStep] = Field(default_factory=list)
    sources: list[TrailSource] = Field(default_factory=list)


class TrailReplayDiff(APIModel):
    changed: bool
    summary_changed: bool
    added_citations: list[str] = Field(default_factory=list)
    removed_citations: list[str] = Field(default_factory=list)


class TrailReplayRequest(APIModel):
    model: str | None = None


class TrailReplayResponse(APIModel):
    trail_id: str
    original_output: Any | None = None
    replay_output: Any
    diff: TrailReplayDiff


__all__ = [
    "AgentTrail",
    "AgentStep",
    "TrailSource",
    "TrailReplayDiff",
    "TrailReplayRequest",
    "TrailReplayResponse",
]
