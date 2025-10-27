"""Pydantic models describing research plans for the Cognitive Scholar loop."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import Field, model_validator

from .base import APIModel


class ResearchPlanStepStatus(str, Enum):
    """Status values surfaced for plan steps."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class ResearchPlanStep(APIModel):
    """Single actionable item within the research plan."""

    id: str
    kind: str
    index: int
    label: str
    query: str | None = None
    tool: str | None = None
    status: ResearchPlanStepStatus = ResearchPlanStepStatus.PENDING
    estimated_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    estimated_duration_seconds: float | None = Field(default=None, ge=0.0)
    actual_tokens: int | None = Field(default=None, ge=0)
    actual_cost_usd: float | None = Field(default=None, ge=0.0)
    actual_duration_seconds: float | None = Field(default=None, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResearchPlan(APIModel):
    """Full ordered plan for the active research loop."""

    session_id: str
    steps: list[ResearchPlanStep] = Field(default_factory=list)
    active_step_id: str | None = None
    version: int = 1
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalise_indexes(self) -> "ResearchPlan":
        """Ensure step indexes remain sequential after (de)serialisation."""

        ordered = sorted(self.steps, key=lambda step: step.index)
        for idx, step in enumerate(ordered):
            step.index = idx
        self.steps = ordered
        return self


class ResearchPlanReorderRequest(APIModel):
    """Payload emitted by the PlanPanel when steps are re-ordered."""

    order: list[str] = Field(
        description="List of step identifiers in their new order.",
    )


class ResearchPlanStepUpdateRequest(APIModel):
    """Inline edit payload for updating a single plan step."""

    query: str | None = None
    tool: str | None = None
    status: ResearchPlanStepStatus | None = None
    estimated_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    estimated_duration_seconds: float | None = Field(default=None, ge=0.0)
    metadata: dict[str, Any] | None = None


class ResearchPlanStepSkipRequest(APIModel):
    """Explicit skip mutation issued by the UI."""

    reason: str | None = Field(
        default=None,
        description="Optional rationale captured when a step is skipped.",
    )


__all__ = [
    "ResearchPlan",
    "ResearchPlanReorderRequest",
    "ResearchPlanStep",
    "ResearchPlanStepSkipRequest",
    "ResearchPlanStepStatus",
    "ResearchPlanStepUpdateRequest",
]

