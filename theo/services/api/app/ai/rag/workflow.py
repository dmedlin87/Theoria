"""Guardrailed RAG workflows for Theo Engine."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, Mapping, Sequence

from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...analytics.telemetry import record_feedback_event
from ...core.version import get_git_sha
from ...db.models import Document, Passage
from ...export.formatters import SCHEMA_VERSION, generate_export_id
from ...models.export import DeliverableAsset, DeliverableManifest, DeliverablePackage
from ...models.search import (
    HybridSearchFilters,
    HybridSearchRequest,
    HybridSearchResult,
)
from ...retriever.hybrid import hybrid_search
from ...telemetry import (
    RAG_CACHE_EVENTS,
    instrument_workflow,
    log_workflow_event,
    set_span_attribute,
)
from ..clients import GenerationError
from ..registry import LLMRegistry, get_llm_registry
from ..router import get_router
from .cache import RAGCache
from .guardrails import (
    GuardrailError,
    _format_anchor,
    apply_guardrail_profile as _guardrails_apply_guardrail_profile,
    build_citations as _guardrails_build_citations,
    build_guardrail_result as _guardrails_build_guardrail_result,
    build_retrieval_digest as _guardrails_build_retrieval_digest,
    ensure_completion_safe as _guardrails_ensure_completion_safe,
    load_guardrail_reference as _guardrails_load_guardrail_reference,
    load_passages_for_osis as _guardrails_load_passages_for_osis,
    validate_model_completion as _guardrails_validate_model_completion,
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
from .prompts import (
    sanitise_json_structure as _prompts_sanitize_json_structure,
    scrub_adversarial_language as _prompts_scrub_adversarial_language,
)

if TYPE_CHECKING:  # pragma: no cover - hints only
    from ..trails import TrailRecorder


LOGGER = logging.getLogger(__name__)

_RAG_TRACER = trace.get_tracer("theo.rag")

_CACHE = RAGCache()
_SENTENCE_PATTERN = re.compile(r"[^.!?]*[.!?]|[^.!?]+$")



class PassageRetriever:
    """Encapsulates passage lookup logic for reuse across workflows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        *,
        query: str | None,
        osis: str | None,
        filters: HybridSearchFilters,
        k: int = 8,
    ) -> list[HybridSearchResult]:
        request = HybridSearchRequest(query=query, osis=osis, filters=filters, k=k)
        results = list(hybrid_search(self._session, request))
        if osis and not any(result.osis_ref for result in results):
            fallback = _guardrails_load_passages_for_osis(self._session, osis)
            if fallback:
                LOGGER.debug(
                    "Hybrid search yielded no OSIS matches; injecting %d fallback passages for %s",
                    len(fallback),
                    osis,
                )
                return fallback
        return results


class GuardedAnswerPipeline:
    """Compose grounded answers while handling guardrails and caching."""

    def __init__(
        self,
        session: Session,
        registry: LLMRegistry,
        *,
        cache: RAGCache = _CACHE,
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
    ) -> RAGAnswer:
        ordered_results, guardrail_profile = _apply_guardrail_profile(results, filters)
        citations = _build_citations(ordered_results)
        if not citations and allow_fallback:
            fallback_result = _load_guardrail_reference(self.session)
            if fallback_result:
                ordered_results = [fallback_result]
                citations = _build_citations(ordered_results)
        if not citations:
            raise GuardrailError(
                "Retrieved passages lacked OSIS references; aborting generation",
                metadata={
                    "code": "retrieval_missing_osis",
                    "guardrail": "retrieval",
                    "suggested_action": "upload",
                },
            )

        cited_results = [result for result in ordered_results if result.osis_ref]
        summary_lines = []
        for idx, citation in enumerate(citations):
            result = cited_results[idx] if idx < len(cited_results) else None
            document_title = (
                citation.document_title
                or (result.document_title if result else None)
                or citation.document_id
            )
            summary_lines.append(
                f"[{citation.index}] {citation.snippet} — {document_title}"
                f" ({citation.osis}, {citation.anchor})"
            )
        summary_text = "\n".join(summary_lines)

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

        context_lines = []
        for citation in citations:
            prompt_snippet = _scrub_adversarial_language(citation.snippet) or ""
            context_lines.append(
                f"[{citation.index}] {prompt_snippet.strip()} (OSIS {citation.osis}, {citation.anchor})"
            )
        prompt_parts = [
            "You are Theo Engine's grounded assistant.",
            "Answer the question strictly from the provided passages.",
            "Cite evidence using the bracketed indices and retain OSIS + anchor in a Sources line.",
            "If the passages do not answer the question, state that explicitly.",
        ]
        if memory_context:
            prompt_parts.append("Prior conversation highlights:")
            for idx, snippet in enumerate(memory_context, start=1):
                sanitized = _scrub_adversarial_language(snippet) or ""
                if sanitized:
                    prompt_parts.append(f"{idx}. {sanitized}")
        sanitized_question = _scrub_adversarial_language(question)
        if sanitized_question:
            prompt_parts.append(f"Question: {sanitized_question}")
        prompt_parts.append("Passages:")
        prompt_parts.extend(context_lines)
        prompt_parts.append("Respond with 2-3 sentences followed by 'Sources:'")
        prompt = "\n".join(prompt_parts)

        retrieval_digest = _build_retrieval_digest(ordered_results)
        last_error: GenerationError | None = None
        cache_key = None
        cache_key_suffix = None
        cache_status = "skipped"

        for candidate in candidates:
            cache_event_logged = False
            cache_key = _build_cache_key(
                user_id=user_id,
                model_label=candidate.name,
                prompt=prompt,
                retrieval_digest=retrieval_digest,
            )
            cache_key_suffix = cache_key[-12:]
            cache_status = "miss"
            cache_hit_payload: RAGAnswer | None = None
            validation_result = None
            model_output = None

            cached_payload = _load_cached_answer(cache_key)
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
                        validation_result = _validate_model_completion(
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
                        validation_result = _validate_model_completion(completion, citations)
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

        answer = RAGAnswer(
            summary=summary_text,
            citations=citations,
            model_name=model_name,
            model_output=model_output,
            guardrail_profile=guardrail_profile,
        )

        if cache_key and model_output and validation_result and cache_status in {
            "miss",
            "refresh",
        }:
            _store_cached_answer(cache_key, answer=answer, validation=validation_result)
            if cache_status == "refresh":
                RAG_CACHE_EVENTS.labels(status="refresh").inc()
                log_workflow_event(
                    "workflow.guardrails_cache",
                    workflow="rag",
                    status="refresh",
                    cache_key_suffix=cache_key_suffix,
                )

        if self.recorder:
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
                    "cache_status": cache_status,
                    "validation": validation_result,
                },
                output_digest=f"{len(summary_lines)} summary lines",
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


def _scrub_adversarial_language(value: str | None) -> str | None:
    return _prompts_scrub_adversarial_language(value)


def _sanitize_json_structure(payload: Any) -> Any:
    return _prompts_sanitize_json_structure(payload)


def _sanitize_markdown_field(value: object | None) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return text.strip()


def _extract_topic_domains(meta: Mapping[str, Any] | None) -> set[str]:
    domains: set[str] = set()
    if not meta:
        return domains
    raw = meta.get("topic_domains") or meta.get("topic_domain")
    if raw is None:
        return domains
    if isinstance(raw, str):
        candidates = re.split(r"[,;]", raw)
    elif isinstance(raw, Iterable):
        candidates = raw
    else:
        return domains
    for item in candidates:
        text = str(item).strip().lower()
        if text:
            domains.add(text)
    return domains


def _apply_guardrail_profile(
    results: Sequence[HybridSearchResult],
    filters: HybridSearchFilters | None,
) -> tuple[list[HybridSearchResult], dict[str, str] | None]:
    return _guardrails_apply_guardrail_profile(results, filters)

def _record_used_citation_feedback(
    session: Session,
    *,
    citations: Sequence[RAGCitation],
    results: Sequence[HybridSearchResult],
    query: str | None,
    recorder: "TrailRecorder | None" = None,
) -> None:
    """Persist feedback events indicating which passages were cited."""

    if not citations:
        return

    result_by_passage: dict[str, HybridSearchResult] = {
        str(result.id): result
        for result in results
        if getattr(result, "id", None)
    }
    user_id: str | None = None
    if recorder is not None and getattr(recorder, "trail", None) is not None:
        user_id = getattr(recorder.trail, "user_id", None)

    for citation in citations:
        passage_id = getattr(citation, "passage_id", None)
        document_id = getattr(citation, "document_id", None)
        if not passage_id and not document_id:
            continue
        context = result_by_passage.get(str(passage_id)) if passage_id else None
        record_feedback_event(
            session,
            action="used_in_answer",
            user_id=user_id,
            query=query,
            document_id=document_id,
            passage_id=passage_id,
            rank=getattr(context, "rank", getattr(citation, "index", None)),
            score=getattr(context, "score", None),
        )


def _build_cache_key(
    *,
    user_id: str | None,
    model_label: str | None,
    prompt: str,
    retrieval_digest: str,
) -> str:
    return _CACHE.build_key(
        user_id=user_id,
        model_label=model_label,
        prompt=prompt,
        retrieval_digest=retrieval_digest,
    )


def _load_cached_answer(key: str) -> dict[str, Any] | None:
    return _CACHE.load(key)


def _store_cached_answer(
    key: str,
    *,
    answer: RAGAnswer,
    validation: dict[str, Any] | None,
) -> None:
    _CACHE.store(key, answer=answer, validation=validation)


def _iter_sentence_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for match in _SENTENCE_PATTERN.finditer(text):
        start, end = match.span()
        sentence = text[start:end].strip()
        if sentence:
            spans.append((start, end, sentence))
    return spans


def _derive_snippet(
    result: HybridSearchResult,
    *,
    text: str | None = None,
    fallback: str | None = None,
) -> str:
    base_text = text if text is not None else result.text or ""
    fallback_value = (fallback if fallback is not None else result.snippet or base_text).strip()
    if not base_text.strip():
        return fallback_value

    start_char = getattr(result, "start_char", None)
    end_char = getattr(result, "end_char", None)
    if start_char is None or end_char is None:
        return fallback_value

    start = max(0, min(len(base_text), start_char))
    end = max(start, min(len(base_text), end_char))
    spans = _iter_sentence_spans(base_text)
    if not spans:
        snippet = base_text[start:end].strip()
        return snippet or fallback_value

    selected_sentences = [
        sentence
        for span_start, span_end, sentence in spans
        if span_end > start and span_start < end
    ]
    if not selected_sentences:
        snippet = base_text[start:end].strip()
        return snippet or fallback_value

    snippet = " ".join(selected_sentences).strip()
    return snippet or fallback_value



def _build_citations(results: Sequence[HybridSearchResult]) -> list[RAGCitation]:
    return _guardrails_build_citations(results)

def _normalise_snippet(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= 240:
        return collapsed
    return collapsed[:237].rstrip() + "…"


def _build_guardrail_result(
    passage: Passage, document: Document | None
) -> HybridSearchResult:
    return _guardrails_build_guardrail_result(passage, document)



def _load_guardrail_reference(session: Session) -> HybridSearchResult | None:
    return _guardrails_load_guardrail_reference(session)



def _load_passages_for_osis(
    session: Session, osis: str, *, limit: int = 3
) -> list[HybridSearchResult]:
    return _guardrails_load_passages_for_osis(session, osis, limit=limit)



def _build_retrieval_digest(results: Sequence[HybridSearchResult]) -> str:
    return _guardrails_build_retrieval_digest(results)


def _validate_model_completion(
    completion: str,
    citations: Sequence[RAGCitation],
) -> dict[str, Any]:
    return _guardrails_validate_model_completion(completion, citations)


def ensure_completion_safe(completion: str | None) -> None:
    _guardrails_ensure_completion_safe(completion)


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
) -> RAGAnswer:
    pipeline = GuardedAnswerPipeline(
        session,
        registry,
        cache=_CACHE,
        recorder=recorder,
    )
    return pipeline.compose(
        question=question,
        results=results,
        model_hint=model_hint,
        filters=filters,
        memory_context=memory_context,
        allow_fallback=allow_fallback,
    )

_REFUSAL_OSIS = "John.1.1"
_REFUSAL_FALLBACK_ANCHOR = "John 1:1"
_REFUSAL_FALLBACK_TITLE = "Guardrail Reference"
_REFUSAL_FALLBACK_SNIPPET = (
    "John 1:1 affirms the Word as divine and life-giving; our responses must remain "
    "grounded in that hope."
)
REFUSAL_MODEL_NAME = "guardrail.refusal"
REFUSAL_MESSAGE = "I’m sorry, but I cannot help with that request."


def _load_refusal_reference(session: Session) -> tuple[Passage | None, Document | None]:
    try:
        record = (
            session.execute(
                select(Passage, Document)
                .join(Document)
                .where(Passage.osis_ref == _REFUSAL_OSIS)
                .limit(1)
            )
            .first()
        )
    except Exception:  # pragma: no cover - defensive fallback
        LOGGER.debug("failed to load guardrail refusal reference", exc_info=True)
        return None, None
    if not record:
        return None, None
    passage, document = record
    return passage, document


def _build_refusal_citation(session: Session) -> RAGCitation:
    passage, document = _load_refusal_reference(session)
    document_title = _REFUSAL_FALLBACK_TITLE
    anchor = _REFUSAL_FALLBACK_ANCHOR
    snippet = _REFUSAL_FALLBACK_SNIPPET
    passage_id = "guardrail-passage"
    document_id = "guardrail-document"

    if passage is not None:
        document_title = getattr(document, "title", None) or _REFUSAL_FALLBACK_TITLE
        passage_id = passage.id
        document_id = passage.document_id
        result = HybridSearchResult(
            id=passage.id,
            document_id=passage.document_id,
            text=passage.text or _REFUSAL_FALLBACK_SNIPPET,
            raw_text=getattr(passage, "raw_text", None),
            osis_ref=passage.osis_ref or _REFUSAL_OSIS,
            start_char=passage.start_char,
            end_char=passage.end_char,
            page_no=passage.page_no,
            t_start=passage.t_start,
            t_end=passage.t_end,
            score=1.0,
            meta=getattr(passage, "meta", None),
            document_title=document_title,
            snippet=passage.text or _REFUSAL_FALLBACK_SNIPPET,
            rank=1,
            highlights=None,
        )
        snippet = _derive_snippet(result, fallback=_REFUSAL_FALLBACK_SNIPPET)
        anchor = _format_anchor(result)

    return RAGCitation(
        index=1,
        osis=_REFUSAL_OSIS,
        anchor=anchor,
        passage_id=passage_id,
        document_id=document_id,
        document_title=document_title,
        snippet=snippet,
        source_url=None,
    )


def build_guardrail_refusal(
    session: Session, *, reason: str | None = None
) -> RAGAnswer:
    citation = _build_refusal_citation(session)
    sources_line = f"[{citation.index}] {citation.osis} ({citation.anchor})"
    model_output = f"{REFUSAL_MESSAGE}\n\nSources: {sources_line}"
    guardrail_profile = {"status": "refused"}
    if reason:
        guardrail_profile["reason"] = reason
    return RAGAnswer(
        summary=REFUSAL_MESSAGE,
        citations=[citation],
        model_name=REFUSAL_MODEL_NAME,
        model_output=model_output,
        guardrail_profile=guardrail_profile,
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
) -> RAGAnswer:
    original_results = list(results)
    filtered_results = [result for result in original_results if result.osis_ref]
    fallback_results: list[HybridSearchResult] = []
    if not filtered_results and osis:
        fallback_results = _load_passages_for_osis(session, osis)
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


def _search(
    session: Session,
    *,
    query: str | None,
    osis: str | None,
    filters: HybridSearchFilters,
    k: int = 8,
) -> list[HybridSearchResult]:
    retriever = PassageRetriever(session)
    return retriever.search(query=query, osis=osis, filters=filters, k=k)


def run_guarded_chat(
    session: Session,
    *,
    question: str,
    osis: str | None = None,
    filters: HybridSearchFilters | None = None,
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
    memory_context: Sequence[str] | None = None,
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
        results = _search(session, query=question, osis=osis, filters=filters)
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
        )
        _record_used_citation_feedback(
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
        results = _search(session, query=question or osis, osis=osis, filters=filters)
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
        _record_used_citation_feedback(
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


def generate_sermon_prep_outline(
    session: Session,
    *,
    topic: str,
    osis: str | None = None,
    filters: HybridSearchFilters | None = None,
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
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
        results = _search(session, query=query, osis=osis, filters=filters, k=10)
        set_span_attribute(span, "workflow.result_count", len(results))
        log_workflow_event(
            "workflow.passages_retrieved",
            workflow="sermon_prep",
            topic=topic,
            result_count=len(results),
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
        _record_used_citation_feedback(
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
        outline = [
            "Opening: situate the passage within the wider canon",
            "Exposition: unpack key theological moves in the passages",
            "Application: connect the insights to contemporary discipleship",
            "Closing: invite response grounded in the cited witnesses",
        ]
        key_points = [
            f"{citation.osis}: {citation.snippet}" for citation in answer.citations[:4]
        ]
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
        results = _search(
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
        _record_used_citation_feedback(
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
        results = _search(session, query="highlights", osis=None, filters=filters, k=8)
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
        _record_used_citation_feedback(
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
        results = _search(session, query=focus, osis=osis, filters=filters, k=6)
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
        _record_used_citation_feedback(
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
        results = _search(
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
        _record_used_citation_feedback(
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


_SUPPORTED_DELIVERABLE_FORMATS = {"markdown", "ndjson", "csv", "pdf"}


def _normalise_formats(formats: Sequence[str]) -> list[str]:
    """Return a deduplicated list of valid deliverable formats."""

    normalised: list[str] = []
    for fmt in formats:
        candidate = fmt.lower()
        if candidate not in _SUPPORTED_DELIVERABLE_FORMATS:
            raise ValueError(f"Unsupported format: {fmt}")
        if candidate not in normalised:
            normalised.append(candidate)
    return normalised


def _build_deliverable_manifest(
    deliverable_type: Literal["sermon", "transcript"],
    *,
    export_id: str | None = None,
    filters: Mapping[str, Any] | None = None,
    model_preset: str | None = None,
    sources: Sequence[str] | None = None,
) -> DeliverableManifest:
    """Create a manifest describing the generated deliverable."""

    manifest_sources = list(dict.fromkeys(list(sources or [])))
    return DeliverableManifest(
        export_id=export_id or generate_export_id(),
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(UTC),
        type=deliverable_type,  # type: ignore[arg-type]
        filters=dict(filters or {}),
        git_sha=get_git_sha(),
        model_preset=model_preset,
        sources=manifest_sources,
    )


def _manifest_front_matter(manifest: DeliverableManifest) -> list[str]:
    lines = [
        "---",
        f"export_id: {_sanitize_markdown_field(manifest.export_id)}",
        f"schema_version: {_sanitize_markdown_field(manifest.schema_version)}",
        f"generated_at: {_sanitize_markdown_field(manifest.generated_at.isoformat())}",
        f"type: {_sanitize_markdown_field(manifest.type)}",
    ]
    if manifest.model_preset:
        lines.append(f"model_preset: {_sanitize_markdown_field(manifest.model_preset)}")
    if manifest.git_sha:
        lines.append(f"git_sha: {_sanitize_markdown_field(manifest.git_sha)}")
    if manifest.sources:
        sources = _sanitize_json_structure(list(manifest.sources))
        lines.append(
            f"sources: {json.dumps(sources, ensure_ascii=False)}"
        )
    if manifest.filters:
        filters = _sanitize_json_structure(dict(manifest.filters))
        lines.append(
            f"filters: {json.dumps(filters, sort_keys=True, ensure_ascii=False)}"
        )
    lines.append("---\n")
    return lines


def _csv_manifest_prefix(manifest: DeliverableManifest) -> str:
    parts = [
        f"export_id={manifest.export_id}",
        f"schema_version={manifest.schema_version}",
        f"type={manifest.type}",
        f"generated_at={manifest.generated_at.isoformat()}",
    ]
    if manifest.git_sha:
        parts.append(f"git_sha={manifest.git_sha}")
    if manifest.model_preset:
        parts.append(f"model_preset={manifest.model_preset}")
    if manifest.sources:
        parts.append(f"sources={json.dumps(manifest.sources)}")
    if manifest.filters:
        parts.append(f"filters={json.dumps(manifest.filters, sort_keys=True)}")
    return ",".join(parts) + "\n"


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _markdown_to_pdf_lines(markdown: str) -> list[str]:
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            lines.append(heading.upper() if heading else "")
            lines.append("")
            continue
        prefix = ""
        content = stripped
        if stripped.startswith(("- ", "* ")):
            prefix = "• "
            content = stripped[2:].strip()
        wrapped = textwrap.wrap(content, width=90) or [""]
        for idx, item in enumerate(wrapped):
            if prefix and idx == 0:
                lines.append(f"{prefix}{item}")
            elif prefix:
                lines.append(f"{' ' * len(prefix)}{item}")
            else:
                lines.append(item)
    return lines or [""]


def _render_markdown_pdf(markdown: str, *, title: str | None = None) -> bytes:
    text_lines = _markdown_to_pdf_lines(markdown)
    heading_lines: list[str] = []
    if title:
        clean_title = title.strip()
        if clean_title:
            heading_lines = [clean_title, ""]
    combined = heading_lines + text_lines
    if not combined:
        combined = [""]

    commands = [
        "BT",
        "/F1 12 Tf",
        "16 TL",
        "72 756 Td",
    ]
    for idx, line in enumerate(combined):
        commands.append(f"({_escape_pdf_text(line)}) Tj")
        if idx != len(combined) - 1:
            commands.append("T*")
    commands.append("ET")
    stream = "\n".join(commands).encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        if not obj.endswith(b"\n"):
            pdf.extend(b"\n")
        pdf.extend(b"endobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(b"trailer\n")
    pdf.extend(f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii"))
    pdf.extend(b"startxref\n")
    pdf.extend(f"{xref_offset}\n".encode("ascii"))
    pdf.extend(b"%%EOF\n")
    return bytes(pdf)


def _render_sermon_markdown(
    manifest: DeliverableManifest, response: SermonPrepResponse
) -> str:
    lines = _manifest_front_matter(manifest)
    lines.append(
        f"# Sermon Prep — {_sanitize_markdown_field(response.topic)}"
    )
    if response.osis:
        lines.append(
            f"Focus Passage: {_sanitize_markdown_field(response.osis)}\n"
        )
    if response.outline:
        lines.append("## Outline")
        for item in response.outline:
            lines.append(f"- {_sanitize_markdown_field(item)}")
        lines.append("")
    if response.key_points:
        lines.append("## Key Points")
        for point in response.key_points:
            lines.append(f"- {_sanitize_markdown_field(point)}")
        lines.append("")
    if response.answer.citations:
        lines.append("## Citations")
        for citation in response.answer.citations:
            osis = _sanitize_markdown_field(citation.osis)
            anchor = _sanitize_markdown_field(citation.anchor)
            snippet = _sanitize_markdown_field(citation.snippet)
            lines.append(f"- {osis} ({anchor}) — {snippet}")
    return "\n".join(lines).strip() + "\n"


def _render_sermon_ndjson(
    manifest: DeliverableManifest, response: SermonPrepResponse
) -> str:
    payload = manifest.model_dump(mode="json")
    lines = [json.dumps(payload, ensure_ascii=False)]
    for idx, item in enumerate(response.outline, start=1):
        lines.append(
            json.dumps(
                {"kind": "outline", "order": idx, "value": item},
                ensure_ascii=False,
            )
        )
    for idx, point in enumerate(response.key_points, start=1):
        lines.append(
            json.dumps(
                {"kind": "key_point", "order": idx, "value": point},
                ensure_ascii=False,
            )
        )
    for citation in response.answer.citations:
        lines.append(
            json.dumps(
                {
                    "kind": "citation",
                    "osis": citation.osis,
                    "anchor": citation.anchor,
                    "snippet": citation.snippet,
                    "document_id": citation.document_id,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines) + "\n"


def _render_sermon_csv(
    manifest: DeliverableManifest, response: SermonPrepResponse
) -> str:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=["osis", "anchor", "snippet", "document_id"]
    )
    writer.writeheader()
    for citation in response.answer.citations:
        writer.writerow(
            {
                "osis": citation.osis,
                "anchor": citation.anchor,
                "snippet": citation.snippet,
                "document_id": citation.document_id,
            }
        )
    return _csv_manifest_prefix(manifest) + buffer.getvalue()


def _render_sermon_pdf(
    manifest: DeliverableManifest, response: SermonPrepResponse
) -> bytes:
    markdown = _render_sermon_markdown(manifest, response)
    title = f"Sermon Prep — {response.topic}" if response.topic else None
    return _render_markdown_pdf(markdown, title=title)


def build_sermon_deliverable(
    response: SermonPrepResponse,
    *,
    formats: Sequence[str],
    filters: Mapping[str, Any] | None = None,
) -> DeliverablePackage:
    """Render sermon prep content as a multi-format deliverable."""

    normalised = _normalise_formats(formats)
    citations = response.answer.citations
    export_id = (
        f"sermon-{citations[0].document_id}"
        if citations
        else generate_export_id()
    )
    manifest_filters: dict[str, Any] = {"topic": response.topic}
    if response.osis:
        manifest_filters["osis"] = response.osis
    if filters:
        manifest_filters["search_filters"] = dict(filters)
    manifest = _build_deliverable_manifest(
        "sermon",
        export_id=export_id,
        filters=manifest_filters,
        model_preset=response.answer.model_name,
        sources=[citation.document_id for citation in citations],
    )
    assets: list[DeliverableAsset] = []
    for fmt in normalised:
        if fmt == "markdown":
            body = _render_sermon_markdown(manifest, response)
            media_type = "text/markdown"
            filename = "sermon.md"
        elif fmt == "ndjson":
            body = _render_sermon_ndjson(manifest, response)
            media_type = "application/x-ndjson"
            filename = "sermon.ndjson"
        elif fmt == "csv":
            body = _render_sermon_csv(manifest, response)
            media_type = "text/csv"
            filename = "sermon.csv"
        elif fmt == "pdf":
            body = _render_sermon_pdf(manifest, response)
            media_type = "application/pdf"
            filename = "sermon.pdf"
        else:  # pragma: no cover - guarded earlier
            raise ValueError(f"Unsupported format: {fmt}")
        assets.append(
            DeliverableAsset(
                format=fmt,
                filename=filename,
                media_type=media_type,
                content=body,
            )
        )
    return DeliverablePackage(manifest=manifest, assets=assets)


def _build_transcript_rows(passages: Sequence[Passage]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for passage in passages:
        speaker = None
        if passage.meta and isinstance(passage.meta, dict):
            speaker = passage.meta.get("speaker")
        rows.append(
            {
                "speaker": speaker or "Narrator",
                "text": passage.text,
                "osis": passage.osis_ref,
                "t_start": passage.t_start,
                "t_end": passage.t_end,
                "page_no": passage.page_no,
                "passage_id": passage.id,
            }
        )
    return rows


def _render_transcript_markdown(
    manifest: DeliverableManifest,
    title: str | None,
    rows: Sequence[dict[str, Any]],
) -> str:
    lines = _manifest_front_matter(manifest)
    heading_subject = title or manifest.filters.get("document_id") or ""
    lines.append(
        f"# Q&A Transcript — {_sanitize_markdown_field(heading_subject)}"
    )
    for row in rows:
        anchor = row.get("osis") or row.get("page_no") or row.get("t_start")
        speaker = _sanitize_markdown_field(row.get("speaker"))
        anchor_text = _sanitize_markdown_field(anchor)
        text = _sanitize_markdown_field(row.get("text"))
        lines.append(f"- **{speaker}** ({anchor_text}): {text}")
    return "\n".join(lines).strip() + "\n"


def _render_transcript_ndjson(
    manifest: DeliverableManifest, rows: Sequence[dict[str, Any]]
) -> str:
    payload = manifest.model_dump(mode="json")
    lines = [json.dumps(payload, ensure_ascii=False)]
    for row in rows:
        lines.append(json.dumps(row, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def _render_transcript_csv(
    manifest: DeliverableManifest, rows: Sequence[dict[str, Any]]
) -> str:
    import csv
    import io

    buffer = io.StringIO()
    fieldnames = list(rows[0].keys()) if rows else ["speaker", "text"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return _csv_manifest_prefix(manifest) + buffer.getvalue()


def _render_transcript_pdf(
    manifest: DeliverableManifest,
    title: str | None,
    rows: Sequence[dict[str, Any]],
) -> bytes:
    markdown = _render_transcript_markdown(manifest, title, rows)
    heading = f"Transcript — {title}" if title else "Transcript"
    return _render_markdown_pdf(markdown, title=heading)


def build_transcript_deliverable(
    session: Session,
    document_id: str,
    *,
    formats: Sequence[str],
) -> DeliverablePackage:
    """Generate transcript exports for the requested document."""

    document = session.get(Document, document_id)
    if document is None:
        raise GuardrailError(
            f"Document {document_id} not found",
            metadata={
                "code": "ingest_document_missing",
                "guardrail": "ingest",
                "suggested_action": "upload",
                "reason": document_id,
            },
        )
    passages = (
        session.query(Passage)
        .filter(Passage.document_id == document_id)
        .order_by(
            Passage.page_no.asc(),
            Passage.t_start.asc(),
            Passage.start_char.asc(),
        )
        .all()
    )
    rows = _build_transcript_rows(passages)
    manifest = _build_deliverable_manifest(
        "transcript",
        export_id=f"transcript-{document_id}",
        filters={"document_id": document_id},
        sources=[document_id],
    )
    normalised = _normalise_formats(formats)
    assets: list[DeliverableAsset] = []
    for fmt in normalised:
        if fmt == "markdown":
            body = _render_transcript_markdown(manifest, document.title, rows)
            media_type = "text/markdown"
            filename = "transcript.md"
        elif fmt == "ndjson":
            body = _render_transcript_ndjson(manifest, rows)
            media_type = "application/x-ndjson"
            filename = "transcript.ndjson"
        elif fmt == "csv":
            body = _render_transcript_csv(manifest, rows)
            media_type = "text/csv"
            filename = "transcript.csv"
        elif fmt == "pdf":
            body = _render_transcript_pdf(manifest, document.title, rows)
            media_type = "application/pdf"
            filename = "transcript.pdf"
        else:  # pragma: no cover - guarded earlier
            raise ValueError(f"Unsupported format: {fmt}")
        assets.append(
            DeliverableAsset(
                format=fmt,
                filename=filename,
                media_type=media_type,
                content=body,
            )
        )
    return DeliverablePackage(manifest=manifest, assets=assets)


def build_sermon_prep_package(
    response: SermonPrepResponse, *, format: str
) -> tuple[str | bytes, str]:
    normalised = format.lower()
    package = build_sermon_deliverable(response, formats=[normalised])
    asset = package.get_asset(normalised)
    return asset.content, asset.media_type


def build_transcript_package(
    session: Session,
    document_id: str,
    *,
    format: str,
) -> tuple[str | bytes, str]:
    normalised = format.lower()
    package = build_transcript_deliverable(session, document_id, formats=[normalised])
    asset = package.get_asset(normalised)
    return asset.content, asset.media_type


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
