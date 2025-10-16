"""Domain entities for the research feature set."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ResearchNoteEvidence:
    """Supporting citation linked to a research note."""

    id: str | None
    source_type: str | None = None
    source_ref: str | None = None
    osis_refs: tuple[str, ...] | None = None
    citation: str | None = None
    snippet: str | None = None
    meta: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ResearchNote:
    """Domain representation of a research note aggregate."""

    id: str
    osis: str
    body: str
    title: str | None = None
    stance: str | None = None
    claim_type: str | None = None
    confidence: float | None = None
    tags: tuple[str, ...] | None = None
    evidences: tuple[ResearchNoteEvidence, ...] = ()
    request_id: str | None = None
    created_by: str | None = None
    tenant_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ResearchNoteEvidenceDraft:
    """Author supplied evidence payload used when creating notes."""

    source_type: str | None = None
    source_ref: str | None = None
    osis_refs: tuple[str, ...] | None = None
    citation: str | None = None
    snippet: str | None = None
    meta: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ResearchNoteDraft:
    """Command payload describing a note prior to persistence."""

    osis: str
    body: str
    title: str | None = None
    stance: str | None = None
    claim_type: str | None = None
    confidence: float | None = None
    tags: tuple[str, ...] | None = None
    evidences: tuple[ResearchNoteEvidenceDraft, ...] = ()
    request_id: str | None = None
    end_user_id: str | None = None
    tenant_id: str | None = None


class ResearchNoteNotFoundError(KeyError):
    """Raised when a requested research note cannot be located."""


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """Domain representation of a theological hypothesis."""

    id: str
    claim: str
    confidence: float
    status: str
    trail_id: str | None = None
    supporting_passage_ids: tuple[str, ...] | None = None
    contradicting_passage_ids: tuple[str, ...] | None = None
    perspective_scores: Mapping[str, float] | None = None
    metadata: Mapping[str, object] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class HypothesisDraft:
    """Creation payload for hypotheses prior to persistence."""

    claim: str
    confidence: float
    status: str
    trail_id: str | None = None
    supporting_passage_ids: tuple[str, ...] | None = None
    contradicting_passage_ids: tuple[str, ...] | None = None
    perspective_scores: Mapping[str, float] | None = None
    metadata: Mapping[str, object] | None = None


class HypothesisNotFoundError(KeyError):
    """Raised when a hypothesis could not be located."""


__all__ = [
    "ResearchNote",
    "ResearchNoteDraft",
    "ResearchNoteEvidence",
    "ResearchNoteEvidenceDraft",
    "ResearchNoteNotFoundError",
    "Hypothesis",
    "HypothesisDraft",
    "HypothesisNotFoundError",
]
