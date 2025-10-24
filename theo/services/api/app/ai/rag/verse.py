"""Verse Copilot orchestration helpers for guardrailed RAG flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from ...models.search import HybridSearchFilters
from ...telemetry import instrument_workflow, log_workflow_event, set_span_attribute
from ..registry import get_llm_registry
from .models import VerseCopilotResponse
from .retrieval import record_used_citation_feedback, search_passages
from .workflow import _guarded_answer_or_refusal

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..trails import TrailRecorder


__all__ = ["generate_verse_brief"]


def generate_verse_brief(
    session: Session,
    *,
    osis: str,
    question: str | None = None,
    filters: HybridSearchFilters | None = None,
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
) -> VerseCopilotResponse:
    """Produce a grounded answer for the verse copilot workflow."""

    filters = filters or HybridSearchFilters()
    with instrument_workflow(
        "verse_copilot",
        osis=osis,
        question_present=bool(question),
        model_hint=model_name,
    ) as span:
        set_span_attribute(
            span,
            "workflow.filters",
            filters.model_dump(exclude_none=True),
        )
        results = search_passages(session, query=question or osis, osis=osis, filters=filters)
        set_span_attribute(span, "workflow.result_count", len(results))
        log_workflow_event(
            "workflow.passages_retrieved",
            workflow="verse_copilot",
            osis=osis,
            result_count=len(results),
        )
        registry = get_llm_registry(session)
        if recorder:
            recorder.log_step(
                tool="hybrid_search",
                action="retrieve_passages",
                input_payload={
                    "query": question or osis,
                    "osis": osis,
                    "filters": filters,
                },
                output_payload=[
                    {
                        "id": result.id,
                        "osis": result.osis_ref,
                        "document_id": result.document_id,
                        "score": getattr(result, "score", None),
                        "snippet": result.snippet,
                    }
                    for result in results
                ],
                output_digest=f"{len(results)} passages",
            )
        answer = _guarded_answer_or_refusal(
            session,
            context="verse_copilot",
            question=question,
            results=results,
            registry=registry,
            model_hint=model_name,
            recorder=recorder,
            filters=filters,
            osis=osis,
        )
        record_used_citation_feedback(
            session,
            citations=answer.citations,
            results=results,
            query=question or osis,
            recorder=recorder,
        )
        set_span_attribute(span, "workflow.citation_count", len(answer.citations))
        set_span_attribute(span, "workflow.summary_length", len(answer.summary))
        log_workflow_event(
            "workflow.answer_composed",
            workflow="verse_copilot",
            citations=len(answer.citations),
        )
        if recorder:
            recorder.record_citations(answer.citations)
        follow_ups = [
            "Compare historical and contemporary commentary",
            "Trace how this verse links to adjacent passages",
            "Surface sermons that emphasise this verse",
        ]
        set_span_attribute(span, "workflow.follow_up_count", len(follow_ups))
        log_workflow_event(
            "workflow.follow_ups_suggested",
            workflow="verse_copilot",
            follow_up_count=len(follow_ups),
        )
        return VerseCopilotResponse(
            osis=osis, question=question, answer=answer, follow_ups=follow_ups
        )
