"""Revision helpers for RAG workflows."""

from __future__ import annotations

from ..reasoning.metacognition import (
    REVISION_QUALITY_THRESHOLD,
    Critique,
    RevisionResult,
)
from .models import (
    FallacyWarningModel,
    ReasoningCritique,
    RevisionDetails,
)


def should_attempt_revision(critique: Critique) -> bool:
    """Determine whether a revision pass is warranted for a critique."""

    if critique.fallacies_found or critique.weak_citations or critique.bias_warnings:
        return True
    if critique.reasoning_quality < REVISION_QUALITY_THRESHOLD:
        return True
    actionable_recommendations = [
        recommendation
        for recommendation in critique.recommendations
        if "acceptable" not in recommendation.lower()
    ]
    return bool(actionable_recommendations)


def critique_to_schema(critique: Critique) -> ReasoningCritique:
    """Convert a dataclass critique into the API schema."""

    fallacies = [
        FallacyWarningModel(
            fallacy_type=fallacy.fallacy_type,
            severity=fallacy.severity,
            description=fallacy.description,
            matched_text=fallacy.matched_text,
            suggestion=fallacy.suggestion,
        )
        for fallacy in critique.fallacies_found
    ]

    return ReasoningCritique(
        reasoning_quality=critique.reasoning_quality,
        fallacies_found=fallacies,
        weak_citations=list(critique.weak_citations),
        alternative_interpretations=list(critique.alternative_interpretations),
        bias_warnings=list(critique.bias_warnings),
        recommendations=list(critique.recommendations),
    )


def revision_to_schema(result: RevisionResult) -> RevisionDetails:
    """Convert a revision result into the API schema."""

    return RevisionDetails(
        original_answer=result.original_answer,
        revised_answer=result.revised_answer,
        critique_addressed=list(result.critique_addressed),
        improvements=result.improvements,
        quality_delta=result.quality_delta,
        revised_critique=critique_to_schema(result.revised_critique),
    )


__all__ = [
    "should_attempt_revision",
    "critique_to_schema",
    "revision_to_schema",
]
