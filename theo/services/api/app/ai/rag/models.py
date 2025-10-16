"""Pydantic models for guardrailed RAG workflows."""

from __future__ import annotations

from datetime import datetime

from collections.abc import MutableMapping
from typing import Literal

from pydantic import Field, model_serializer

from ...models.base import APIModel


class RAGCitation(APIModel):
    index: int
    osis: str
    anchor: str
    passage_id: str
    document_id: str
    document_title: str | None = None
    snippet: str
    source_url: str | None = None
    raw_snippet: str | None = Field(default=None, exclude=True)


class RAGAnswer(APIModel):
    summary: str
    citations: list[RAGCitation]
    model_name: str | None = None
    model_output: str | None = None
    guardrail_profile: dict[str, str] | None = None
    fallacy_warnings: list["FallacyWarningModel"] = Field(default_factory=list)
    critique: "ReasoningCritique | None" = None
    revision: "RevisionDetails | None" = None
    reasoning_trace: "ReasoningTrace | None" = None

    @model_serializer(mode="wrap")
    def _include_guardrail_profile(self, handler):
        """Ensure the ``guardrail_profile`` key is present in serialized output."""

        data = handler(self)
        if isinstance(data, MutableMapping):
            data.setdefault("guardrail_profile", None)
            data.setdefault("reasoning_trace", None)
        return data


class ReasoningTraceEvidence(APIModel):
    id: str
    text: str
    label: str | None = None
    citation_ids: list[int] = Field(default_factory=list)


class ReasoningTraceStep(APIModel):
    id: str
    label: str
    detail: str | None = None
    outcome: str | None = None
    status: Literal["pending", "in_progress", "supported", "contradicted", "uncertain", "complete"] | None = None
    confidence: float | None = None
    citations: list[int] = Field(default_factory=list)
    evidence: list[ReasoningTraceEvidence] = Field(default_factory=list)
    children: list["ReasoningTraceStep"] = Field(default_factory=list)


class ReasoningTrace(APIModel):
    summary: str | None = None
    strategy: str | None = None
    steps: list[ReasoningTraceStep] = Field(default_factory=list)


ReasoningTraceStep.model_rebuild()
ReasoningTrace.model_rebuild()


class FallacyWarningModel(APIModel):
    fallacy_type: str
    severity: str
    description: str
    matched_text: str
    suggestion: str | None = None


class ReasoningCritique(APIModel):
    reasoning_quality: int
    fallacies_found: list[FallacyWarningModel]
    weak_citations: list[str]
    alternative_interpretations: list[str]
    bias_warnings: list[str]
    recommendations: list[str]


class RevisionDetails(APIModel):
    original_answer: str
    revised_answer: str
    critique_addressed: list[str]
    improvements: str
    quality_delta: int
    revised_critique: ReasoningCritique


class VerseCopilotResponse(APIModel):
    osis: str
    question: str | None = None
    answer: RAGAnswer
    follow_ups: list[str]


class SermonPrepResponse(APIModel):
    topic: str
    osis: str | None = None
    outline: list[str]
    key_points: list[str]
    answer: RAGAnswer


class ComparativeAnalysisResponse(APIModel):
    osis: str
    participants: list[str]
    comparisons: list[str]
    answer: RAGAnswer


class MultimediaDigestResponse(APIModel):
    collection: str | None
    highlights: list[str]
    answer: RAGAnswer


class DevotionalResponse(APIModel):
    osis: str
    focus: str
    reflection: str
    prayer: str
    answer: RAGAnswer


class CorpusCurationReport(APIModel):
    since: datetime
    documents_processed: int
    summaries: list[str]


class CollaborationResponse(APIModel):
    thread: str
    synthesized_view: str
    answer: RAGAnswer


__all__ = [
    "CollaborationResponse",
    "ComparativeAnalysisResponse",
    "CorpusCurationReport",
    "DevotionalResponse",
    "FallacyWarningModel",
    "MultimediaDigestResponse",
    "ReasoningTrace",
    "ReasoningTraceEvidence",
    "ReasoningTraceStep",
    "RAGAnswer",
    "RAGCitation",
    "ReasoningCritique",
    "RevisionDetails",
    "SermonPrepResponse",
    "VerseCopilotResponse",
]
