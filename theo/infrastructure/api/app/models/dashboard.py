"""Pydantic schemas for dashboard summaries."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import Field

from .base import APIModel


class MetricTrend(str, Enum):
    """Enumeration describing trend direction for dashboard metrics."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class DashboardMetric(APIModel):
    """Aggregate metric rendered in the dashboard header."""

    id: str = Field(description="Stable identifier for UI keying")
    label: str = Field(description="Human readable label for the metric")
    value: float = Field(description="Current value for the metric")
    unit: str | None = Field(default=None, description="Optional unit suffix")
    delta_percentage: float | None = Field(
        default=None, description="Week-over-week percentage change for the metric"
    )
    trend: MetricTrend = Field(
        default=MetricTrend.FLAT,
        description="Direction of the metric change compared to the previous period",
    )


class DashboardActivity(APIModel):
    """Structured entry shown in the activity feed."""

    id: str
    type: Literal[
        "document_ingested",
        "note_created",
        "discovery_published",
        "notebook_updated",
    ]
    title: str
    description: str | None = None
    occurred_at: datetime
    href: str | None = None


class DashboardQuickAction(APIModel):
    """Quick link surfaced in the dashboard."""

    id: str
    label: str
    href: str
    description: str | None = None
    icon: str | None = Field(default=None, description="Emoji or icon identifier")


class DashboardUserSummary(APIModel):
    """Simple representation of the active principal for personalization."""

    name: str
    plan: str | None = None
    timezone: str | None = None
    last_login: datetime | None = None


class DashboardSummary(APIModel):
    """Top-level payload returned to the dashboard UI."""

    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp at which the summary was assembled",
    )
    user: DashboardUserSummary
    metrics: list[DashboardMetric]
    activity: list[DashboardActivity]
    quick_actions: list[DashboardQuickAction]


__all__ = [
    "MetricTrend",
    "DashboardMetric",
    "DashboardActivity",
    "DashboardQuickAction",
    "DashboardUserSummary",
    "DashboardSummary",
]
