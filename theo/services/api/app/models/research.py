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
