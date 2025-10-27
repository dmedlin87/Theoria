"""Reasoning helpers for the guardrailed chat pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from theo.application.ports.ai_registry import GenerationError

from ..reasoning.chain_of_thought import parse_chain_of_thought
from ..reasoning.metacognition import critique_reasoning, revise_with_critique
from ..registry import LLMModel
from .models import (
    RAGCitation,
    ReasoningCritique,
    ReasoningTrace,
    RevisionDetails,
)
from .revisions import critique_to_schema, revision_to_schema, should_attempt_revision
from .reasoning_trace import build_reasoning_trace_from_completion
from .telemetry import record_revision_event

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..trails import TrailRecorder


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ReasoningOutcome:
    """Artifacts produced by the reasoning review stage."""

    answer: str
    original_answer: str
    critique: ReasoningCritique | None
    revision: RevisionDetails | None
    reasoning_trace: ReasoningTrace | None


def run_reasoning_review(
    *,
    answer: str,
    citations: Sequence[RAGCitation],
    selected_model: LLMModel | None,
    recorder: "TrailRecorder | None" = None,
    mode: str | None = None,
) -> ReasoningOutcome:
    """Apply critique and revision steps to an LLM answer."""

    original_answer = answer
    critique_schema: ReasoningCritique | None = None
    revision_schema: RevisionDetails | None = None

    chain_of_thought = parse_chain_of_thought(answer)
    reasoning_text = (
        chain_of_thought.raw_thinking.strip()
        if chain_of_thought.raw_thinking
        else answer
    )
    citation_payloads = [
        citation.model_dump(exclude_none=True)
        for citation in citations
    ]

    try:
        critique_obj = critique_reasoning(
            reasoning_trace=reasoning_text,
            answer=answer,
            citations=citation_payloads,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        LOGGER.warning("Failed to critique model output", exc_info=exc)
        if recorder:
            recorder.log_step(
                tool="rag.critique",
                action="critique_reasoning",
                status="failed",
                input_payload={"model_output": answer[:2000]},
                error_message=str(exc),
            )
    else:
        critique_schema = critique_to_schema(critique_obj)
        if should_attempt_revision(critique_obj) and selected_model is not None:
            try:
                revision_client = selected_model.build_client()
                revision_result = revise_with_critique(
                    original_answer=answer,
                    critique=critique_obj,
                    client=revision_client,
                    model=selected_model.model,
                    reasoning_trace=reasoning_text,
                    citations=citation_payloads,
                )
            except GenerationError as exc:
                LOGGER.warning("Revision attempt failed: %s", exc)
                if recorder:
                    recorder.log_step(
                        tool="rag.revise",
                        action="revise_with_critique",
                        status="failed",
                        input_payload={
                            "original_quality": critique_obj.reasoning_quality,
                        },
                        output_digest=str(exc),
                        error_message=str(exc),
                    )
            else:
                revision_schema = revision_to_schema(revision_result)
                if revision_result.revised_answer.strip():
                    answer = revision_result.revised_answer
                record_revision_event(
                    quality_delta=revision_result.quality_delta,
                    addressed=len(revision_result.critique_addressed),
                )
                if recorder:
                    recorder.log_step(
                        tool="rag.revise",
                        action="revise_with_critique",
                        input_payload={
                            "original_quality": critique_obj.reasoning_quality,
                        },
                        output_payload={
                            "quality_delta": revision_result.quality_delta,
                            "addressed": revision_result.critique_addressed,
                            "revised_quality": (
                                revision_result.revised_critique.reasoning_quality
                            ),
                        },
                        output_digest=(
                            f"delta={revision_result.quality_delta}, "
                            f"addressed={len(revision_result.critique_addressed)}"
                        ),
                    )

    reasoning_trace = build_reasoning_trace_from_completion(answer, mode=mode)

    return ReasoningOutcome(
        answer=answer,
        original_answer=original_answer,
        critique=critique_schema,
        revision=revision_schema,
        reasoning_trace=reasoning_trace,
    )


__all__ = ["ReasoningOutcome", "run_reasoning_review"]
