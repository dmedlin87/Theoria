"""Research reconciliation orchestration helpers for guardrailed RAG flows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from sqlalchemy.orm import Session

from ...models.search import HybridSearchFilters
from ...telemetry import instrument_workflow, log_workflow_event, set_span_attribute
from ..registry import get_llm_registry
from .models import CollaborationResponse
from .retrieval import record_used_citation_feedback, search_passages
from .workflow import _guarded_answer_or_refusal

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..trails import TrailRecorder


__all__ = ["run_research_reconciliation"]


def run_research_reconciliation(
    session: Session,
    *,
    thread: str,
    osis: str,
    viewpoints: Sequence[str],
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
) -> CollaborationResponse:
    """Reconcile multiple viewpoints for a passage using grounded generation."""

    filters = HybridSearchFilters()
    with instrument_workflow(
        "research_reconciliation",
        thread=thread,
        osis=osis,
        viewpoint_count=len(viewpoints),
        model_hint=model_name,
    ) as span:
        set_span_attribute(
            span,
            "workflow.viewpoints",
            list(viewpoints),
        )
        results = search_passages(
            session, query="; ".join(viewpoints), osis=osis, filters=filters, k=10
        )
        set_span_attribute(span, "workflow.result_count", len(results))
        log_workflow_event(
            "workflow.passages_retrieved",
            workflow="research_reconciliation",
            thread=thread,
            result_count=len(results),
        )
        if recorder:
            recorder.log_step(
                tool="hybrid_search",
                action="retrieve_passages",
                input_payload={
                    "query": "; ".join(viewpoints),
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
        registry = get_llm_registry(session)
        question_text = f"Reconcile viewpoints for {osis} in {thread}"
        answer = _guarded_answer_or_refusal(
            session,
            context="research_reconciliation",
            question=question_text,
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
            query=question_text,
            recorder=recorder,
        )
        set_span_attribute(span, "workflow.citation_count", len(answer.citations))
        log_workflow_event(
            "workflow.answer_composed",
            workflow="research_reconciliation",
            citations=len(answer.citations),
        )
        if recorder:
            recorder.record_citations(answer.citations)
        synthesis_lines = [
            f"{citation.osis}: {citation.snippet}" for citation in answer.citations
        ]
        synthesized_view = "\n".join(synthesis_lines)
        return CollaborationResponse(
            thread=thread, synthesized_view=synthesized_view, answer=answer
        )
