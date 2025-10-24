"""Guardrailed RAG workflows for Theo Engine."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, Sequence

from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.application.ports.ai_registry import GenerationError
from theo.services.api.app.persistence_models import Document, Passage

from ...models.search import HybridSearchFilters, HybridSearchResult
from ...telemetry import (
    RAG_CACHE_EVENTS,
    instrument_workflow,
    log_workflow_event,
    set_span_attribute,
)
from ..reasoning.chain_of_thought import parse_chain_of_thought
from ..reasoning.metacognition import critique_reasoning, revise_with_critique
from ..registry import LLMModel, LLMRegistry, get_llm_registry
from ..router import get_router
from ..trails import TrailStepDigest
from .cache_ops import (
    DEFAULT_CACHE,
    RAGCache,
    build_cache_key,
    load_cached_answer,
    store_cached_answer,
)
from .exports import (
    build_sermon_deliverable,
    build_sermon_prep_package,
    build_transcript_deliverable,
    build_transcript_package,
)
from .guardrail_helpers import (
    GuardrailError,
    apply_guardrail_profile,
    build_citations,
    build_retrieval_digest,
    ensure_completion_safe,
    load_guardrail_reference,
    load_passages_for_osis,
    validate_model_completion,
)
from .models import (
    CollaborationResponse,
    ComparativeAnalysisResponse,
    CorpusCurationReport,
    DevotionalResponse,
    MultimediaDigestResponse,
    RAGAnswer,
    RAGCitation,
    ReasoningCritique,
    ReasoningTrace,
    RevisionDetails,
    SermonPrepResponse,
    VerseCopilotResponse,
)
from .prompts import PromptContext
from .refusals import REFUSAL_MESSAGE, REFUSAL_MODEL_NAME, build_guardrail_refusal
from .revisions import critique_to_schema, revision_to_schema, should_attempt_revision
from .reasoning_trace import build_reasoning_trace_from_completion
from .retrieval import record_used_citation_feedback, search_passages

if TYPE_CHECKING:  # pragma: no cover - hints only
    from ..trails import TrailRecorder


LOGGER = logging.getLogger(__name__)

_RAG_TRACER = trace.get_tracer("theo.rag")



class GuardedAnswerPipeline:
    """Compose grounded answers while handling guardrails and caching."""

    def __init__(
        self,
        session: Session,
        registry: LLMRegistry,
        *,
        cache: RAGCache = DEFAULT_CACHE,
        recorder: "TrailRecorder | None" = None,
    ) -> None:
        self.session = session
        self.registry = registry
        self.cache = cache
        self.recorder = recorder

    def compose(
        self,
        *,
        question: str | None,
        results: Sequence[HybridSearchResult],
        model_hint: str | None = None,
        filters: HybridSearchFilters | None = None,
        memory_context: Sequence[str] | None = None,
        allow_fallback: bool = False,
        mode: str | None = None,
    ) -> RAGAnswer:
        ordered_results, guardrail_profile = apply_guardrail_profile(results, filters)
        citations = build_citations(ordered_results)
        if not citations and allow_fallback:
            fallback_result = load_guardrail_reference(self.session)
            if fallback_result:
                ordered_results = [fallback_result]
                citations = build_citations(ordered_results)
        if not citations:
            raise GuardrailError(
                "Retrieved passages lacked OSIS references; aborting generation",
                metadata={
                    "code": "retrieval_missing_osis",
                    "guardrail": "retrieval",
                    "suggested_action": "upload",
                },
            )

        prompt_context = PromptContext(
            citations=citations,
            filters=filters,
            memory_context=memory_context,
        )
        summary_text, summary_lines = prompt_context.build_summary(ordered_results)

        model_output = None
        model_name = None
        validation_result: dict[str, Any] | None = None
        cache_status = "skipped"
        cache_key: str | None = None
        cache_key_suffix: str | None = None

        user_id = None
        if self.recorder and getattr(self.recorder, "trail", None) is not None:
            user_id = getattr(self.recorder.trail, "user_id", None)

        router = get_router(self.session, registry=self.registry)
        candidates = list(router.iter_candidates("rag", model_hint))
        if not candidates:
            raise GenerationError("No language models are available for workflow 'rag'")

        prompt = prompt_context.build_prompt(question)

        retrieval_digest = build_retrieval_digest(ordered_results)
        last_error: GenerationError | None = None
        selected_model: LLMModel | None = None

        cache_key = None
        cache_key_suffix = None
        cache_status = "skipped"

        for candidate in candidates:
            selected_model = candidate
            cache_event_logged = False
            cache_key = build_cache_key(
                user_id=user_id,
                model_label=candidate.name,
                prompt=prompt,
                retrieval_digest=retrieval_digest,
                cache=self.cache,
            )
            cache_key_suffix = cache_key[-12:]
            cache_status = "miss"
            cache_hit_payload: RAGAnswer | None = None
            validation_result = None
            model_output = None

            cached_payload = load_cached_answer(cache_key, cache=self.cache)
            if cached_payload:
                cache_status = "hit"
                try:
                    cache_hit_payload = RAGAnswer.model_validate(cached_payload.get("answer"))
                except Exception:
                    LOGGER.debug(
                        "invalid cached answer payload for key %s", cache_key, exc_info=True
                    )
                    cache_hit_payload = None

                if cache_hit_payload and cache_hit_payload.model_output:
                    try:
                        validation_result = validate_model_completion(
                            cache_hit_payload.model_output, citations
                        )
                        ensure_completion_safe(cache_hit_payload.model_output)
                    except GuardrailError as exc:
                        cache_status = "stale"
                        self.cache.delete(cache_key)
                        RAG_CACHE_EVENTS.labels(status="stale").inc()
                        log_workflow_event(
                            "workflow.guardrails_cache",
                            workflow="rag",
                            status="stale",
                            cache_key_suffix=cache_key_suffix,
                        )
                        cache_event_logged = True
                        if self.recorder:
                            self.recorder.log_step(
                                tool="rag.cache",
                                action="invalidate",
                                input_payload={"cache_key_suffix": cache_key_suffix},
                                status="failed",
                                error_message=str(exc),
                            )
                        cache_hit_payload = None
                        validation_result = None
                    else:
                        model_output = cache_hit_payload.model_output
                        model_name = cached_payload.get("model_name", candidate.name)
                else:
                    cache_status = "stale"

            if cache_status == "hit" and model_output:
                RAG_CACHE_EVENTS.labels(status="hit").inc()
                log_workflow_event(
                    "workflow.guardrails_cache",
                    workflow="rag",
                    status="hit",
                    cache_key_suffix=cache_key_suffix,
                )
            elif not cache_event_logged:
                if cache_status == "hit":
                    cache_status = "stale"
                if cache_status == "stale":
                    RAG_CACHE_EVENTS.labels(status="stale").inc()
                    log_workflow_event(
                        "workflow.guardrails_cache",
                        workflow="rag",
                        status="stale",
                        cache_key_suffix=cache_key_suffix,
                    )
                else:
                    RAG_CACHE_EVENTS.labels(status="miss").inc()
                    log_workflow_event(
                        "workflow.guardrails_cache",
                        workflow="rag",
                        status="miss",
                        cache_key_suffix=cache_key_suffix,
                    )

            if self.recorder and cache_key:
                self.recorder.log_step(
                    tool="rag.cache",
                    action="lookup",
                    input_payload={"cache_key_suffix": cache_key_suffix},
                    output_payload={"status": cache_status},
                    output_digest=cache_status,
                )

            if model_output:
                break

            llm_payload = {
                "prompt": prompt,
                "model": candidate.model,
                "registry_name": candidate.name,
            }
            if mode:
                llm_payload["reasoning_mode"] = mode
            try:
                with _RAG_TRACER.start_as_current_span("rag.execute_generation") as span:
                    span.set_attribute("rag.candidate", candidate.name)
                    span.set_attribute("rag.model_label", candidate.model)
                    span.set_attribute("rag.cache_status", cache_status)
                    if cache_key_suffix:
                        span.set_attribute("rag.cache_key_suffix", cache_key_suffix)
                    span.set_attribute("rag.prompt_tokens", max(len(prompt) // 4, 0))
                    try:
                        routed_generation = router.execute_generation(
                            workflow="rag",
                            model=candidate,
                            prompt=prompt,
                            reasoning_mode=mode,
                        )
                    except GenerationError as inner_exc:
                        span.record_exception(inner_exc)
                        span.set_attribute("rag.guardrails_cache_final", cache_status)
                        raise
                    span.set_attribute("rag.latency_ms", routed_generation.latency_ms)
                    span.set_attribute(
                        "rag.completion_tokens",
                        max(len(routed_generation.output) // 4, 0)
                        if routed_generation.output
                        else 0,
                    )

                    completion = routed_generation.output
                    if self.recorder:
                        self.recorder.log_step(
                            tool="llm.generate",
                            action="generate_grounded_answer",
                            input_payload=llm_payload,
                            output_payload={
                                "completion": completion,
                                "latency_ms": routed_generation.latency_ms,
                                "cost": routed_generation.cost,
                            },
                            output_digest=f"{len(completion)} characters",
                        )
                    sources_line = "; ".join(
                        f"[{citation.index}] {citation.osis} ({citation.anchor})" for citation in citations
                    )
                    has_citations_line = bool(re.search(r"Sources:\s*\[\d+]", completion))
                    if not has_citations_line:
                        completion = completion.strip() + f"\n\nSources: {sources_line}"
                    try:
                        validation_result = validate_model_completion(completion, citations)
                        ensure_completion_safe(completion)
                    except GuardrailError as exc:
                        span.record_exception(exc)
                        log_workflow_event(
                            "workflow.guardrails_validation",
                            workflow="rag",
                            status="failed",
                            cache_status=cache_status,
                            cache_key_suffix=cache_key_suffix,
                        )
                        if self.recorder:
                            self.recorder.log_step(
                                tool="guardrails.validate",
                                action="check_citations",
                                status="failed",
                                input_payload={
                                    "cache_status": cache_status,
                                    "cache_key_suffix": cache_key_suffix,
                                },
                                output_payload={"completion": completion},
                                error_message=str(exc),
                            )
                        span.set_attribute("rag.guardrails_cache_final", cache_status)
                        raise
                    model_output = completion
                    model_name = candidate.name
                    if cache_status == "stale":
                        cache_status = "refresh"
                    span.set_attribute("rag.guardrails_cache_final", cache_status)
                    break
            except GenerationError as exc:
                last_error = exc
                if self.recorder:
                    self.recorder.log_step(
                        tool="llm.generate",
                        action="generate_grounded_answer",
                        status="failed",
                        input_payload=llm_payload,
                        output_digest=str(exc),
                        error_message=str(exc),
                    )
                continue

        if not model_output:
            if last_error is not None:
                raise last_error
            raise GenerationError("Language model routing failed to produce a completion")
        if validation_result:
            log_workflow_event(
                "workflow.guardrails_validation",
                workflow="rag",
                status=validation_result.get("status", "passed"),
                cache_status=cache_status,
                cache_key_suffix=cache_key_suffix,
                citation_count=validation_result.get("citation_count"),
                cited_indices=validation_result.get("cited_indices"),
            )
            if self.recorder:
                self.recorder.log_step(
                    tool="guardrails.validate",
                    action="check_citations",
                    input_payload={
                        "cache_status": cache_status,
                        "cache_key_suffix": cache_key_suffix,
                    },
                    output_payload=validation_result,
                    output_digest=f"status={validation_result.get('status', 'passed')}",
                )

        critique_schema: ReasoningCritique | None = None
        revision_schema: RevisionDetails | None = None
        original_model_output = model_output

        reasoning_text_for_critique = None

        if model_output:
            chain_of_thought = parse_chain_of_thought(model_output)
            reasoning_text_for_critique = (
                chain_of_thought.raw_thinking.strip()
                if chain_of_thought.raw_thinking
                else model_output
            )
            citation_payloads = [
                citation.model_dump(exclude_none=True)
                for citation in citations
            ]
            try:
                critique_obj = critique_reasoning(
                    reasoning_trace=reasoning_text_for_critique,
                    answer=model_output,
                    citations=citation_payloads,
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                LOGGER.warning("Failed to critique model output", exc_info=exc)
                if self.recorder:
                    self.recorder.log_step(
                        tool="rag.critique",
                        action="critique_reasoning",
                        status="failed",
                        input_payload={"model_output": model_output[:2000]},
                        error_message=str(exc),
                    )
            else:
                critique_schema = critique_to_schema(critique_obj)
                if should_attempt_revision(critique_obj) and selected_model is not None:
                    try:
                        revision_client = selected_model.build_client()
                        revision_result = revise_with_critique(
                            original_answer=model_output,
                            critique=critique_obj,
                            client=revision_client,
                            model=selected_model.model,
                            reasoning_trace=reasoning_text_for_critique,
                            citations=citation_payloads,
                        )
                    except GenerationError as exc:
                        LOGGER.warning("Revision attempt failed: %s", exc)
                        if self.recorder:
                            self.recorder.log_step(
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
                            model_output = revision_result.revised_answer
                        log_workflow_event(
                            "workflow.reasoning_revision",
                            workflow="rag",
                            status="applied",
                            quality_delta=revision_result.quality_delta,
                            addressed=len(revision_result.critique_addressed),
                        )
                        if self.recorder:
                            self.recorder.log_step(
                                tool="rag.revise",
                                action="revise_with_critique",
                                input_payload={
                                    "original_quality": critique_obj.reasoning_quality,
                                },
                                output_payload={
                                    "quality_delta": revision_result.quality_delta,
                                    "addressed": revision_result.critique_addressed,
                                    "revised_quality": revision_result.revised_critique.reasoning_quality,
                                },
                                output_digest=(
                                    f"delta={revision_result.quality_delta}, "
                                    f"addressed={len(revision_result.critique_addressed)}"
                                ),
                            )

        reasoning_trace: ReasoningTrace | None = None
        if model_output:
            reasoning_trace = build_reasoning_trace_from_completion(
                model_output,
                mode=mode,
            )

        answer = RAGAnswer(
            summary=summary_text,
            citations=citations,
            model_name=model_name,
            model_output=model_output,
            guardrail_profile=guardrail_profile,
            fallacy_warnings=(
                critique_schema.fallacies_found if critique_schema else []
            ),
            critique=critique_schema,
            revision=revision_schema,
            reasoning_trace=reasoning_trace,
        )

        if cache_key and model_output and validation_result and cache_status in {
            "miss",
            "refresh",
        }:
            store_cached_answer(
                cache_key,
                answer=answer,
                validation=validation_result,
                cache=self.cache,
            )
            if cache_status == "refresh":
                RAG_CACHE_EVENTS.labels(status="refresh").inc()
                log_workflow_event(
                    "workflow.guardrails_cache",
                    workflow="rag",
                    status="refresh",
                    cache_key_suffix=cache_key_suffix,
                )

        if self.recorder:
            key_entities: list[str] = []
            for citation in citations:
                label_parts = [citation.osis]
                anchor = getattr(citation, "anchor", None)
                document_title = getattr(citation, "document_title", None)
                if anchor:
                    label_parts.append(anchor)
                elif document_title:
                    label_parts.append(document_title)
                label = " - ".join(part for part in label_parts if part)
                if label:
                    key_entities.append(label)
            recommended_actions: list[str] = []
            if critique_schema and critique_schema.recommendations:
                recommended_actions.extend(critique_schema.recommendations)
            if revision_schema and revision_schema.improvements:
                recommended_actions.append(revision_schema.improvements)
            digest_payload = TrailStepDigest(
                summary=summary_text,
                key_entities=key_entities,
                recommended_actions=recommended_actions,
            )

            compose_step = self.recorder.log_step(
                tool="rag.compose",
                action="compose_answer",
                input_payload={
                    "question": question,
                    "citations": [
                        {
                            "index": citation.index,
                            "osis": citation.osis,
                            "anchor": citation.anchor,
                            "snippet": citation.snippet,
                            "passage_id": citation.passage_id,
                        }
                        for citation in citations
                    ],
                },
                output_payload={
                    "summary": summary_text,
                    "model_name": model_name,
                    "model_output": model_output,
                    "original_model_output": original_model_output,
                    "critique": critique_schema.model_dump(exclude_none=True)
                    if critique_schema
                    else None,
                    "revision": revision_schema.model_dump(exclude_none=True)
                    if revision_schema
                    else None,
                    "cache_status": cache_status,
                    "validation": validation_result,
                },
                output_digest=f"{len(summary_lines)} summary lines",
                digest=digest_payload,
                significant=True,
            )

            passage_ids = [
                citation.passage_id
                for citation in citations
                if getattr(citation, "passage_id", None)
            ]
            osis_refs = [
                citation.osis for citation in citations if getattr(citation, "osis", None)
            ]
            self.recorder.record_retrieval_snapshot(
                retrieval_hash=retrieval_digest,
                passage_ids=passage_ids,
                osis_refs=osis_refs,
                step=compose_step,
            )

        return answer


def _guarded_answer(
    session: Session,
    *,
    question: str | None,
    results: Sequence[HybridSearchResult],
    registry: LLMRegistry,
    model_hint: str | None = None,
    recorder: "TrailRecorder | None" = None,
    filters: HybridSearchFilters | None = None,
    memory_context: Sequence[str] | None = None,
    allow_fallback: bool = False,
    mode: str | None = None,
) -> RAGAnswer:
    pipeline = GuardedAnswerPipeline(
        session,
        registry,
        cache=DEFAULT_CACHE,
        recorder=recorder,
    )
    return pipeline.compose(
        question=question,
        results=results,
        model_hint=model_hint,
        filters=filters,
        memory_context=memory_context,
        allow_fallback=allow_fallback,
        mode=mode,
    )

def _guarded_answer_or_refusal(
    session: Session,
    *,
    context: str,
    question: str | None,
    results: Sequence[HybridSearchResult],
    registry: LLMRegistry,
    model_hint: str | None = None,
    recorder: "TrailRecorder | None" = None,
    filters: HybridSearchFilters | None = None,
    memory_context: Sequence[str] | None = None,
    osis: str | None = None,
    allow_fallback: bool | None = None,
    mode: str | None = None,
) -> RAGAnswer:
    original_results = list(results)
    filtered_results = [result for result in original_results if result.osis_ref]
    fallback_results: list[HybridSearchResult] = []
    if not filtered_results and osis:
        fallback_results = load_passages_for_osis(session, osis)
        if fallback_results:
            filtered_results = fallback_results
    candidate_results = filtered_results or original_results
    enable_fallback = allow_fallback if allow_fallback is not None else False

    try:
        return _guarded_answer(
            session,
            question=question,
            results=candidate_results,
            registry=registry,
            model_hint=model_hint,
            recorder=recorder,
            filters=filters,
            memory_context=memory_context,
            allow_fallback=enable_fallback,
            mode=mode,
        )
    except GuardrailError as exc:
        if not getattr(exc, "safe_refusal", False):
            raise
        LOGGER.warning(
            "Guardrail enforcement failed for %s: %s",
            context,
            exc,
            extra={"workflow": context},
        )
        return build_guardrail_refusal(session, reason=str(exc))


def run_guarded_chat(
    session: Session,
    *,
    question: str,
    osis: str | None = None,
    filters: HybridSearchFilters | None = None,
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
    memory_context: Sequence[str] | None = None,
    mode: str | None = None,
) -> RAGAnswer:
    filters = filters or HybridSearchFilters()
    with instrument_workflow(
        "chat",
        question_present=bool(question),
        model_hint=model_name,
    ) as span:
        set_span_attribute(
            span,
            "workflow.filters",
            filters.model_dump(exclude_none=True),
        )
        if mode:
            set_span_attribute(span, "workflow.reasoning_mode", mode)
        results = search_passages(session, query=question, osis=osis, filters=filters)
        set_span_attribute(span, "workflow.result_count", len(results))
        log_workflow_event(
            "workflow.passages_retrieved",
            workflow="chat",
            result_count=len(results),
        )
        registry = get_llm_registry(session)
        if recorder:
            recorder.log_step(
                tool="hybrid_search",
                action="retrieve_passages",
                input_payload={
                    "query": question,
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
            context="chat",
            question=question,
            results=results,
            registry=registry,
            model_hint=model_name,
            recorder=recorder,
            filters=filters,
            memory_context=memory_context,
            osis=osis,
            mode=mode,
        )
        record_used_citation_feedback(
            session,
            citations=answer.citations,
            results=results,
            query=question,
            recorder=recorder,
        )
        set_span_attribute(span, "workflow.citation_count", len(answer.citations))
        set_span_attribute(span, "workflow.summary_length", len(answer.summary))
        log_workflow_event(
            "workflow.answer_composed",
            workflow="chat",
            citations=len(answer.citations),
        )
        if recorder:
            recorder.record_citations(answer.citations)
        return answer


def generate_verse_brief(
    session: Session,
    *,
    osis: str,
    question: str | None = None,
    filters: HybridSearchFilters | None = None,
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
) -> VerseCopilotResponse:
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


def _select_diverse_key_points(citations: list["RAGCitation"], limit: int) -> list[str]:
    """
    Select diverse key points from citations, preferring different books and avoiding duplicates.

    Args:
        citations: List of RAG citations to select from
        limit: Maximum number of key points to return

    Returns:
        List of formatted key points as "osis: snippet"
    """
    if not citations:
        return []

    selected: list[str] = []
    seen_books: set[str] = set()
    seen_osis: set[str] = set()

    # First pass: select citations from different books
    for citation in citations:
        if len(selected) >= limit:
            break
        # Extract book name from OSIS (e.g., "Gen.1.1" -> "Gen")
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
) -> SermonPrepResponse:
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
        results = search_passages(session, query=query, osis=osis, filters=filters, k=10)
        set_span_attribute(span, "workflow.result_count", len(results))
        log_workflow_event(
            "workflow.passages_retrieved",
            workflow="sermon_prep",
            topic=topic,
            result_count=len(results),
        )

        # Validate sufficient sources are available
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

        # Use custom outline template or default liturgical structure
        outline = outline_template or [
            "Opening: situate the passage within the wider canon",
            "Exposition: unpack key theological moves in the passages",
            "Application: connect the insights to contemporary discipleship",
            "Closing: invite response grounded in the cited witnesses",
        ]

        # Extract diverse key points from citations
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
) -> ComparativeAnalysisResponse:
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
        comparisons = []
        for citation in answer.citations:
            comparisons.append(
                f"{citation.document_title or citation.document_id}: {citation.snippet}"
            )
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
) -> MultimediaDigestResponse:
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
) -> DevotionalResponse:
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


def run_corpus_curation(
    session: Session,
    *,
    since: datetime | None = None,
    recorder: "TrailRecorder | None" = None,
) -> CorpusCurationReport:
    with instrument_workflow(
        "corpus_curation",
        since=since.isoformat() if since else "auto-7d",
    ) as span:
        if since is None:
            since = datetime.now(UTC) - timedelta(days=7)
        set_span_attribute(span, "workflow.effective_since", since.isoformat())
        rows = (
            session.execute(
                select(Document)
                .where(Document.created_at >= since)
                .order_by(Document.created_at.asc())
            )
            .scalars()
            .all()
        )
        set_span_attribute(span, "workflow.documents_processed", len(rows))
        log_workflow_event(
            "workflow.documents_loaded",
            workflow="corpus_curation",
            count=len(rows),
        )
        summaries: list[str] = []
        for document in rows:
            primary_topic = None
            if document.bib_json and isinstance(document.bib_json, dict):
                primary_topic = document.bib_json.get("primary_topic")
            if isinstance(document.topics, list) and not primary_topic:
                primary_topic = document.topics[0] if document.topics else None
            topic_label = primary_topic or "Uncategorised"
            summaries.append(
                f"{document.title or document.id} — {topic_label} ({document.collection or 'general'})"
            )
        set_span_attribute(span, "workflow.summary_count", len(summaries))
        if recorder:
            recorder.log_step(
                tool="corpus_curation",
                action="summarise_documents",
                input_payload={"since": since.isoformat()},
                output_payload=summaries,
                output_digest=f"{len(summaries)} summaries",
            )
        return CorpusCurationReport(
            since=since, documents_processed=len(rows), summaries=summaries
        )


def run_research_reconciliation(
    session: Session,
    *,
    thread: str,
    osis: str,
    viewpoints: Sequence[str],
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
) -> CollaborationResponse:
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


__all__ = [
    "CollaborationResponse",
    "ComparativeAnalysisResponse",
    "CorpusCurationReport",
    "DevotionalResponse",
    "GuardrailError",
    "REFUSAL_MODEL_NAME",
    "REFUSAL_MESSAGE",
    "MultimediaDigestResponse",
    "RAGAnswer",
    "RAGCitation",
    "SermonPrepResponse",
    "VerseCopilotResponse",
    "build_sermon_deliverable",
    "build_sermon_prep_package",
    "build_guardrail_refusal",
    "build_transcript_deliverable",
    "build_transcript_package",
    "generate_comparative_analysis",
    "generate_devotional_flow",
    "generate_multimedia_digest",
    "generate_sermon_prep_outline",
    "generate_verse_brief",
    "run_guarded_chat",
    "run_corpus_curation",
    "run_research_reconciliation",
]
