"""Schemas describing structured audit artefacts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .base import APIModel


class AuditClaimEvidence(APIModel):
    source_type: str
    source_id: str | None = None
    title: str | None = None
    uri: str | None = None
    snippet: str | None = None
    hash: str | None = None
    meta: dict[str, Any] | None = None


class AuditClaimMetrics(APIModel):
    faithfulness: float | None = None
    answer_relevance: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    selfcheck_disagreement: float | None = None
    audit_score: float | None = None


class AuditClaimTimestamps(APIModel):
    drafted_at: datetime | None = None
    verified_at: datetime | None = None


class AuditClaimCard(APIModel):
    claim_id: str
    answer_id: str
    text: str
    mode: str
    label: str
    confidence: float | None = None
    evidence: list[AuditClaimEvidence] = Field(default_factory=list)
    verification_methods: list[str] = Field(default_factory=list)
    metrics: AuditClaimMetrics | None = None
    timestamps: AuditClaimTimestamps | None = None
    escalations: list[dict[str, Any]] = Field(default_factory=list)


class AuditLogMetadata(APIModel):
    mode: str | None = None
    audit_score: float | None = None
    claim_cards: list[AuditClaimCard] = Field(default_factory=list)
    extras: dict[str, Any] | None = None


__all__ = [
    "AuditClaimCard",
    "AuditClaimEvidence",
    "AuditClaimMetrics",
    "AuditClaimTimestamps",
    "AuditLogMetadata",
]
