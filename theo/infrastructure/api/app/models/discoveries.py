"""Pydantic schemas for discovery endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices

from .base import APIModel, BaseModel, Field


class DiscoveryMetadata(APIModel):
    relatedDocuments: list[str] | None = None
    relatedVerses: list[str] | None = None
    relatedTopics: list[str] | None = None
    patternData: dict[str, Any] | None = None
    contradictionData: dict[str, Any] | None = None
    gapData: dict[str, Any] | None = None
    connectionData: dict[str, Any] | None = None
    trendData: dict[str, Any] | None = None
    anomalyData: dict[str, Any] | None = None


class DiscoveryResponse(APIModel):
    id: str
    type: str = Field(alias="discovery_type")
    title: str
    description: str
    confidence: float
    relevanceScore: float = Field(alias="relevance_score")
    viewed: bool
    createdAt: datetime = Field(alias="created_at")
    userReaction: str | None = Field(default=None, alias="user_reaction")
    metadata: DiscoveryMetadata | dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("meta", "metadata"),
    )


class DiscoveryStats(APIModel):
    total: int
    unviewed: int
    byType: dict[str, int]
    averageConfidence: float


class DiscoveryListResponse(APIModel):
    discoveries: list[DiscoveryResponse]
    stats: DiscoveryStats


class DiscoveryFeedbackRequest(BaseModel):
    helpful: bool


__all__ = [
    "DiscoveryFeedbackRequest",
    "DiscoveryListResponse",
    "DiscoveryMetadata",
    "DiscoveryResponse",
    "DiscoveryStats",
]
