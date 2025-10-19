"""Data models for Cognitive Scholar reasoning timeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ReasoningStepType(str, Enum):
    """Types of reasoning steps in the research workflow."""
    
    UNDERSTAND = "understand"
    GATHER = "gather"
    TENSIONS = "tensions"
    DRAFT = "draft"
    CRITIQUE = "critique"
    REVISE = "revise"
    SYNTHESIZE = "synthesize"


class ReasoningStepStatus(str, Enum):
    """Execution status of a reasoning step."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReasoningStep(BaseModel):
    """A single step in the reasoning timeline."""
    
    id: str
    step_type: ReasoningStepType
    status: ReasoningStepStatus = ReasoningStepStatus.PENDING
    title: str
    description: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    citations: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    output_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReasoningTimeline(BaseModel):
    """Complete reasoning timeline for a research session."""
    
    session_id: str
    question: str
    steps: list[ReasoningStep]
    current_step_index: int = 0
    total_duration_ms: int = 0
    status: str = "running"  # running, paused, completed, failed
    created_at: datetime
    updated_at: datetime


__all__ = [
    "ReasoningStepType",
    "ReasoningStepStatus",
    "ReasoningStep",
    "ReasoningTimeline",
]
