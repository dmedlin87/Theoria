"""Deliverable-focused RAG workflow helpers extracted from the legacy module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from sqlalchemy.orm import Session

from ...models.search import HybridSearchFilters
from ...telemetry import instrument_workflow, log_workflow_event, set_span_attribute
from ..registry import get_llm_registry
from .guardrail_helpers import GuardrailError
from .models import (
    ComparativeAnalysisResponse,
    DevotionalResponse,
    MultimediaDigestResponse,
    RAGCitation,
    SermonPrepResponse,
)
from .retrieval import record_used_citation_feedback

if TYPE_CHECKING:  # pragma: no cover - hints only
    from ..trails import TrailRecorder


def _select_diverse_key_points(citations: list["RAGCitation"], limit: int) -> list[str]:
    """Select diverse key points from citations, preferring different books."""

    if not citations:
        return []

    selected: list[str] = []
    seen_books: set[str] = set()
    seen_osis: set[str] = set()

    # First pass: select citations from different books
    for citation in citations:
        if len(selected) >= limit:
            break
        book = citation.osis.split(".")[0] if "." in citation.osis else citation.osis
        if book not in seen_books and citation.osis not in seen_osis:
            selected.append(f"{citation.osis}: {citation.snippet}")
            seen_books.add(book)
            seen_osis.add(citation.osis)

    # Second pass: fill remaining slots with any unique citations
    for citation in citations:
        if len(selected) >= limit:
            break
        if citation.osis not in seen_osis:
            selected.append(f"{citation.osis}: {citation.snippet}")
            seen_osis.add(citation.osis)

    return selected


def generate_sermon_prep_outline(
    session: Session,
    *,
    topic: str,
    osis: str | None = None,
    filters: HybridSearchFilters | None = None,
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
    outline_template: list[str] | None = None,
    key_points_limit: int = 4,
):
    from .chat import _guarded_answer_or_refusal  # Imported lazily to avoid cycles.

    filters = filters or HybridSearchFilters()
    query = topic if not osis else f"{topic} {osis}"
    with instrument_workflow(
        "sermon_prep",
        topic=topic,
        has_osis=bool(osis),
        model_hint=model_name,
    ) as span:
        set_span_attribute(
            span,
            "workflow.filters",
            filters.model_dump(exclude_none=True),
        )
        from .workflow import search_passages

        results = search_passages(session, query=query, osis=osis, filters=filters, k=10)
        set_span_attribute(span, "workflow.result_count", len(results))
        log_workflow_event(
            "workflow.passages_retrieved",
            workflow="sermon_prep",
            topic=topic,
            result_count=len(results),
        )

        if not results:
            raise GuardrailError(
                "Insufficient biblical sources found for this topic. Try broadening your search or adjusting filters.",
                safe_refusal=True,
                metadata={
                    "code": "sermon_prep_insufficient_context",
                    "guardrail": "retrieval",
                    "category": "insufficient_context",
                    "severity": "error",
                    "suggested_action": "search",
                    "filters": filters.model_dump(exclude_none=True),
                },
            )

        registry = get_llm_registry(session)
        if recorder:
            recorder.log_step(
                tool="hybrid_search",
                action="retrieve_passages",
                input_payload={
                    "query": query,
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
            context="sermon_prep",
            question=query,
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
            query=query,
            recorder=recorder,
        )
        set_span_attribute(span, "workflow.citation_count", len(answer.citations))
        set_span_attribute(span, "workflow.summary_length", len(answer.summary))
        log_workflow_event(
            "workflow.answer_composed",
            workflow="sermon_prep",
            citations=len(answer.citations),
        )
        if recorder:
            recorder.record_citations(answer.citations)

        outline = outline_template or [
            "Opening: situate the passage within the wider canon",
            "Exposition: unpack key theological moves in the passages",
            "Application: connect the insights to contemporary discipleship",
            "Closing: invite response grounded in the cited witnesses",
        ]

        key_points = _select_diverse_key_points(
            answer.citations, limit=key_points_limit
        )
        set_span_attribute(span, "workflow.outline_steps", len(outline))
        set_span_attribute(span, "workflow.key_point_count", len(key_points))
        log_workflow_event(
            "workflow.outline_ready",
            workflow="sermon_prep",
            outline_steps=len(outline),
        )
        log_workflow_event(
            "workflow.key_points_selected",
            workflow="sermon_prep",
            key_point_count=len(key_points),
        )
        return SermonPrepResponse(
            topic=topic, osis=osis, outline=outline, key_points=key_points, answer=answer
        )


def generate_comparative_analysis(
    session: Session,
    *,
    osis: str,
    participants: Sequence[str],
    model_name: str | None = None,
):
    from .chat import _guarded_answer_or_refusal

    filters = HybridSearchFilters()
    with instrument_workflow(
        "comparative_analysis",
        osis=osis,
        participant_count=len(participants),
        model_hint=model_name,
    ) as span:
        set_span_attribute(
            span,
            "workflow.participants",
            list(participants),
        )
        from .workflow import search_passages

        results = search_passages(
            session, query="; ".join(participants), osis=osis, filters=filters, k=12
        )
        set_span_attribute(span, "workflow.result_count", len(results))
        log_workflow_event(
            "workflow.passages_retrieved",
            workflow="comparative_analysis",
            osis=osis,
            result_count=len(results),
        )
        registry = get_llm_registry(session)
        question_text = f"How do {', '.join(participants)} interpret {osis}?"
        answer = _guarded_answer_or_refusal(
            session,
            context="comparative_analysis",
            question=question_text,
            results=results,
            registry=registry,
            model_hint=model_name,
            filters=filters,
            osis=osis,
        )
        record_used_citation_feedback(
            session,
            citations=answer.citations,
            results=results,
            query=question_text,
        )
        set_span_attribute(span, "workflow.citation_count", len(answer.citations))
        log_workflow_event(
            "workflow.answer_composed",
            workflow="comparative_analysis",
            citations=len(answer.citations),
        )
        comparisons = [
            f"{citation.document_title or citation.document_id}: {citation.snippet}"
            for citation in answer.citations
        ]
        return ComparativeAnalysisResponse(
            osis=osis,
            participants=list(participants),
            comparisons=comparisons,
            answer=answer,
        )


def generate_multimedia_digest(
    session: Session,
    *,
    collection: str | None = None,
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
):
    from .chat import _guarded_answer_or_refusal

    filters = HybridSearchFilters(
        collection=collection, source_type="audio" if collection else None
    )
    with instrument_workflow(
        "multimedia_digest",
        collection=collection or "all",
        model_hint=model_name,
    ) as span:
        set_span_attribute(
            span,
            "workflow.filters",
            filters.model_dump(exclude_none=True),
        )
        from .workflow import search_passages

        results = search_passages(session, query="highlights", osis=None, filters=filters, k=8)
        set_span_attribute(span, "workflow.result_count", len(results))
        log_workflow_event(
            "workflow.passages_retrieved",
            workflow="multimedia_digest",
            result_count=len(results),
        )
        if recorder:
            recorder.log_step(
                tool="hybrid_search",
                action="retrieve_passages",
                input_payload={
                    "query": "highlights",
                    "osis": None,
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
        answer = _guarded_answer_or_refusal(
            session,
            context="multimedia_digest",
            question="What are the key audio/video insights?",
            results=results,
            registry=registry,
            model_hint=model_name,
            recorder=recorder,
            filters=filters,
            osis=None,
        )
        record_used_citation_feedback(
            session,
            citations=answer.citations,
            results=results,
            query="What are the key audio/video insights?",
            recorder=recorder,
        )
        set_span_attribute(span, "workflow.citation_count", len(answer.citations))
        highlights = [
            f"{citation.document_title or citation.document_id}: {citation.snippet}"
            for citation in answer.citations
        ]
        if recorder:
            recorder.record_citations(answer.citations)
        return MultimediaDigestResponse(
            collection=collection, highlights=highlights, answer=answer
        )


def generate_devotional_flow(
    session: Session,
    *,
    osis: str,
    focus: str,
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
):
    from .chat import _guarded_answer_or_refusal

    filters = HybridSearchFilters()
    with instrument_workflow(
        "devotional",
        osis=osis,
        focus=focus,
        model_hint=model_name,
    ) as span:
        set_span_attribute(
            span,
            "workflow.filters",
            filters.model_dump(exclude_none=True),
        )
        from .workflow import search_passages

        results = search_passages(session, query=focus, osis=osis, filters=filters, k=6)
        set_span_attribute(span, "workflow.result_count", len(results))
        log_workflow_event(
            "workflow.passages_retrieved",
            workflow="devotional",
            osis=osis,
            result_count=len(results),
        )
        if recorder:
            recorder.log_step(
                tool="hybrid_search",
                action="retrieve_passages",
                input_payload={
                    "query": focus,
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
        question_text = f"Devotional focus: {focus}"
        answer = _guarded_answer_or_refusal(
            session,
            context="devotional",
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
            workflow="devotional",
            citations=len(answer.citations),
        )
        if recorder:
            recorder.record_citations(answer.citations)
        reflection = "\n".join(
            f"Reflect on {citation.osis} ({citation.anchor}): {citation.snippet}"
            for citation in answer.citations[:3]
        )
        prayer_lines = [
            f"Spirit, help me embody {citation.snippet}"
            for citation in answer.citations[:2]
        ]
        prayer = "\n".join(prayer_lines)
        return DevotionalResponse(
            osis=osis, focus=focus, reflection=reflection, prayer=prayer, answer=answer
        )


__all__ = [
    "generate_sermon_prep_outline",
    "generate_comparative_analysis",
    "generate_multimedia_digest",
    "generate_devotional_flow",
]

