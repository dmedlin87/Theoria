"""Pydantic schemas for research endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .base import APIModel


class ScriptureVerse(APIModel):
    osis: str
    translation: str
    text: str
    book: str | None = None
    chapter: int | None = None
    verse: int | None = None


class ScriptureResponse(APIModel):
    osis: str
    translation: str
    verses: list[ScriptureVerse]
    meta: dict[str, Any] | None = None


class CrossReference(APIModel):
    source: str
    target: str
    weight: float | None = None
    relation_type: str | None = None
    summary: str | None = None
    dataset: str | None = None


class CrossReferenceResponse(APIModel):
    osis: str
    results: list[CrossReference]
    total: int


class VariantReading(APIModel):
    id: str
    osis: str
    category: str
    reading: str
    note: str | None = None
    source: str | None = None
    witness: str | None = None
    translation: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class VariantApparatusResponse(APIModel):
    osis: str
    readings: list[VariantReading] = Field(default_factory=list)
    total: int


class HistoricityEntry(APIModel):
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    summary: str | None = None
    source: str | None = None
    url: str | None = None
    tags: list[str] = Field(default_factory=list)
    score: float


class HistoricitySearchResponse(APIModel):
    query: str
    results: list[HistoricityEntry] = Field(default_factory=list)
    total: int


class FallacyDetection(APIModel):
    id: str
    name: str
    category: str
    description: str
    severity: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    matches: list[str] = Field(default_factory=list)


class FallacyDetectRequest(APIModel):
    text: str
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class FallacyDetectResponse(APIModel):
    text: str
    detections: list[FallacyDetection] = Field(default_factory=list)
    total: int


class ReportClaim(APIModel):
    statement: str
    stance: str | None = None
    support: list[str] | None = None


class ReportBuildRequest(APIModel):
    osis: str
    stance: str
    claims: list[ReportClaim] | None = None
    historicity_query: str | None = None
    narrative_text: str | None = None
    include_fallacies: bool = False
    variants_limit: int | None = Field(default=None, ge=1, le=50)
    citations_limit: int = Field(default=5, ge=1, le=20)
    min_fallacy_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ResearchReportSection(APIModel):
    title: str
    summary: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)


class ResearchReport(APIModel):
    osis: str
    stance: str
    summary: str
    sections: list[ResearchReportSection] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class ResearchReportResponse(APIModel):
    report: ResearchReport


class MorphToken(APIModel):
    osis: str
    surface: str
    lemma: str | None = None
    morph: str | None = None
    gloss: str | None = None
    position: int | None = None


class MorphologyResponse(APIModel):
    osis: str
    tokens: list[MorphToken]


class NoteEvidenceCreate(APIModel):
    source_type: str | None = None
    source_ref: str | None = None
    osis_refs: list[str] | None = None
    citation: str | None = None
    snippet: str | None = None
    meta: dict[str, Any] | None = None


class ResearchNoteCreate(APIModel):
    osis: str
    body: str
    title: str | None = None
    stance: str | None = None
    claim_type: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] | None = None
    evidences: list[NoteEvidenceCreate] | None = None


class ResearchNoteUpdate(APIModel):
    osis: str | None = None
    body: str | None = None
    title: str | None = None
    stance: str | None = None
    claim_type: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] | None = None
    evidences: list[NoteEvidenceCreate] | None = None


class NoteEvidence(APIModel):
    id: str
    source_type: str | None = None
    source_ref: str | None = None
    osis_refs: list[str] | None = None
    citation: str | None = None
    snippet: str | None = None
    meta: dict[str, Any] | None = None


class ResearchNote(APIModel):
    id: str
    osis: str
    body: str
    title: str | None = None
    stance: str | None = None
    claim_type: str | None = None
    confidence: float | None = None
    tags: list[str] | None = None
    evidences: list[NoteEvidence] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ResearchNotesResponse(APIModel):
    osis: str
    notes: list[ResearchNote]
    total: int


class ResearchNoteResponse(APIModel):
    note: ResearchNote


class ContradictionItem(APIModel):
    id: str
    osis_a: str
    osis_b: str
    summary: str | None = None
    source: str | None = None
    tags: list[str] | None = None
    weight: float = 1.0


class ContradictionSearchResponse(APIModel):
    items: list[ContradictionItem] = Field(default_factory=list)


class GeoPlaceItem(APIModel):
    slug: str
    name: str
    lat: float | None = None
    lng: float | None = None
    confidence: float | None = None
    aliases: list[str] | None = None
    sources: dict[str, Any] | list[dict[str, Any]] | None = None


class GeoPlaceSearchResponse(APIModel):
    items: list[GeoPlaceItem] = Field(default_factory=list)
