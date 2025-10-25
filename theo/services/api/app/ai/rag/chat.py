"""Guardrailed chat workflows and helpers for Theo Engine."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence
from sqlalchemy.orm import Session

from theo.application.ports.ai_registry import GenerationError
from ...models.search import HybridSearchFilters, HybridSearchResult
from theo.application.facades.telemetry import instrument_workflow, set_span_attribute
from ..registry import LLMModel, LLMRegistry, get_llm_registry
from ..router import get_router
from ..trails import TrailStepDigest
from .cache import extract_cache_key_suffix, record_cache_status
from .cache_ops import (
    DEFAULT_CACHE,
    RAGCache,
    build_cache_key,
    load_cached_answer,
    store_cached_answer,
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
    SermonPrepResponse,
    VerseCopilotResponse,
)
from .prompts import PromptContext
from .reasoning import run_reasoning_review
from .refusals import REFUSAL_MESSAGE, REFUSAL_MODEL_NAME, build_guardrail_refusal
from .retrieval import record_used_citation_feedback, search_passages
from .telemetry import (
    generation_span,
    record_answer_event,
    record_generation_result,
    record_passages_retrieved,
    record_validation_event,
    set_final_cache_status,
)

if TYPE_CHECKING:  # pragma: no cover - hints only
    from ..trails import TrailRecorder
    from collections.abc import Callable

    from .deliverables import (
        generate_comparative_analysis as _GenerateComparativeAnalysis,
        generate_devotional_flow as _GenerateDevotionalFlow,
        generate_multimedia_digest as _GenerateMultimediaDigest,
        generate_sermon_prep_outline as _GenerateSermonPrepOutline,
    )
    from .exports import (
        build_sermon_deliverable as _BuildSermonDeliverable,
        build_sermon_prep_package as _BuildSermonPrepPackage,
        build_transcript_deliverable as _BuildTranscriptDeliverable,
        build_transcript_package as _BuildTranscriptPackage,
    )
else:  # pragma: no cover - runtime fallback
    from collections.abc import Callable


LOGGER = logging.getLogger(__name__)


def _missing_deliverable_hook(name: str) -> Callable[..., Any]:
    def _missing(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(
            "Deliverable hook '%s' has not been configured. "
            "Import 'theo.services.api.app.ai.rag.workflow' to initialise the"
            " compatibility layer." % name
        )

    return _missing


@dataclass(frozen=True)
class DeliverableHooks:
    generate_sermon_prep_outline: "Callable[..., SermonPrepResponse]"
    generate_comparative_analysis: "Callable[..., ComparativeAnalysisResponse]"
    generate_devotional_flow: "Callable[..., DevotionalResponse]"
    generate_multimedia_digest: "Callable[..., MultimediaDigestResponse]"
    build_sermon_deliverable: "Callable[..., Any]"
    build_sermon_prep_package: "Callable[..., Any]"
    build_transcript_deliverable: "Callable[..., Any]"
    build_transcript_package: "Callable[..., Any]"


_deliverable_hooks: DeliverableHooks | None = None


generate_sermon_prep_outline = _missing_deliverable_hook(
    "generate_sermon_prep_outline"
)
generate_comparative_analysis = _missing_deliverable_hook(
    "generate_comparative_analysis"
)
generate_devotional_flow = _missing_deliverable_hook("generate_devotional_flow")
generate_multimedia_digest = _missing_deliverable_hook(
    "generate_multimedia_digest"
)
build_sermon_deliverable = _missing_deliverable_hook("build_sermon_deliverable")
build_sermon_prep_package = _missing_deliverable_hook("build_sermon_prep_package")
build_transcript_deliverable = _missing_deliverable_hook(
    "build_transcript_deliverable"
)
build_transcript_package = _missing_deliverable_hook("build_transcript_package")


def configure_deliverable_hooks(hooks: DeliverableHooks) -> DeliverableHooks:
    """Install deliverable helpers while preserving compatibility exports."""

    global _deliverable_hooks
    _deliverable_hooks = hooks

    globals().update(
        generate_sermon_prep_outline=hooks.generate_sermon_prep_outline,
        generate_comparative_analysis=hooks.generate_comparative_analysis,
        generate_devotional_flow=hooks.generate_devotional_flow,
        generate_multimedia_digest=hooks.generate_multimedia_digest,
        build_sermon_deliverable=hooks.build_sermon_deliverable,
        build_sermon_prep_package=hooks.build_sermon_prep_package,
        build_transcript_deliverable=hooks.build_transcript_deliverable,
        build_transcript_package=hooks.build_transcript_package,
    )

    return hooks


def get_deliverable_hooks() -> DeliverableHooks | None:
    """Return the currently configured deliverable hooks, if any."""

    return _deliverable_hooks



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
            cache_key_suffix = extract_cache_key_suffix(cache_key)
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
                        record_cache_status(
                            "stale", cache_key_suffix=cache_key_suffix
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
                record_cache_status("hit", cache_key_suffix=cache_key_suffix)
            elif not cache_event_logged:
                if cache_status == "hit":
                    cache_status = "stale"
                record_cache_status(cache_status, cache_key_suffix=cache_key_suffix)

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
                with generation_span(
                    candidate.name,
                    candidate.model,
                    cache_status=cache_status,
                    cache_key_suffix=cache_key_suffix,
                    prompt=prompt,
                ) as span:
                    try:
                        routed_generation = router.execute_generation(
                            workflow="rag",
                            model=candidate,
                            prompt=prompt,
                            reasoning_mode=mode,
                        )
                    except GenerationError as inner_exc:
                        if span is not None and hasattr(span, "record_exception"):
                            span.record_exception(inner_exc)
                        set_final_cache_status(span, cache_status)
                        raise
                    record_generation_result(
                        span,
                        latency_ms=routed_generation.latency_ms,
                        completion=routed_generation.output,
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
                        if span is not None and hasattr(span, "record_exception"):
                            span.record_exception(exc)
                        record_validation_event(
                            "failed",
                            cache_status=cache_status,
                            cache_key_suffix=cache_key_suffix,
                            citation_count=None,
                            cited_indices=None,
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
                        set_final_cache_status(span, cache_status)
                        raise
                    model_output = completion
                    model_name = candidate.name
                    if cache_status == "stale":
                        cache_status = "refresh"
                    set_final_cache_status(span, cache_status)
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
            record_validation_event(
                validation_result.get("status", "passed"),
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

        critique_schema = None
        revision_schema = None
        original_model_output = model_output
        reasoning_trace = None

        if model_output:
            reasoning_outcome = run_reasoning_review(
                answer=model_output,
                citations=citations,
                selected_model=selected_model,
                recorder=self.recorder,
                mode=mode,
            )
            model_output = reasoning_outcome.answer
            critique_schema = reasoning_outcome.critique
            revision_schema = reasoning_outcome.revision
            reasoning_trace = reasoning_outcome.reasoning_trace
            original_model_output = reasoning_outcome.original_answer

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
                record_cache_status("refresh", cache_key_suffix=cache_key_suffix)

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
        record_passages_retrieved(result_count=len(results))
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
        record_answer_event(citation_count=len(answer.citations))
        if recorder:
            recorder.record_citations(answer.citations)
        return answer


