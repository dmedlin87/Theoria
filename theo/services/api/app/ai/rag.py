"""Guardrailed RAG workflows for Theo Engine."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Literal, Mapping, Sequence, TypeVar

try:  # pragma: no cover - optional dependency guard
    from redis import asyncio as redis_asyncio
except ImportError:  # pragma: no cover - redis is optional at runtime
    redis_asyncio = None  # type: ignore[assignment]

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..core.version import get_git_sha
from ..db.models import Document, Passage
from ..export.formatters import SCHEMA_VERSION, generate_export_id
from ..models.base import APIModel
from ..models.export import DeliverableAsset, DeliverableManifest, DeliverablePackage
from ..models.search import HybridSearchFilters, HybridSearchRequest, HybridSearchResult
from ..retriever.hybrid import hybrid_search
from ..telemetry import instrument_workflow, log_workflow_event, set_span_attribute
from .clients import GenerationError
from .registry import LLMRegistry, get_llm_registry
from .router import get_router

if TYPE_CHECKING:  # pragma: no cover - hints only
    from .trails import TrailRecorder


LOGGER = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30 * 60
_CITATION_ENTRY_PATTERN = re.compile(r"^\[(?P<index>\d+)]\s*(?P<osis>[^()]+?)\s*\((?P<anchor>[^()]+)\)$")

_redis_client: Any = None


class GuardrailError(GenerationError):
    """Raised when an answer violates grounding requirements."""


class RAGCitation(APIModel):
    index: int
    osis: str
    anchor: str
    passage_id: str
    document_id: str
    document_title: str | None = None
    snippet: str


class RAGAnswer(APIModel):
    summary: str
    citations: list[RAGCitation]
    model_name: str | None = None
    model_output: str | None = None


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


T = TypeVar("T")


def _get_cache_client() -> Any:
    """Return a memoized Redis client or ``None`` if unavailable."""

    global _redis_client

    if redis_asyncio is None:
        return None
    if _redis_client is not None:
        return _redis_client

    try:
        settings = get_settings()
        _redis_client = redis_asyncio.from_url(  # type: ignore[assignment]
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    except Exception:  # pragma: no cover - network/config errors
        LOGGER.debug("failed to initialise redis client", exc_info=True)
        _redis_client = None
    return _redis_client


def _run_redis_command(operation: Callable[[Any], Awaitable[T]]) -> T | None:
    """Execute an async redis command from synchronous code."""

    client = _get_cache_client()
    if client is None:
        return None

    async def _runner() -> T:
        return await operation(client)

    try:
        return asyncio.run(_runner())
    except RuntimeError as exc:  # pragma: no cover - nested loop guard
        if "running event loop" in str(exc).lower():
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_runner())
            finally:
                loop.close()
        raise
    except Exception:  # pragma: no cover - redis failures logged at debug
        LOGGER.debug("redis command failed", exc_info=True)
        return None


def _normalise_cache_segment(value: str | None, default: str) -> str:
    segment = value or default
    return re.sub(r"[^a-zA-Z0-9._-]", "_", segment)


def _build_cache_key(
    *,
    user_id: str | None,
    model_label: str | None,
    prompt: str,
    retrieval_digest: str,
) -> str:
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    version = _normalise_cache_segment(get_git_sha() or "dev", "dev")
    user_segment = _normalise_cache_segment(user_id, "anon")
    model_segment = _normalise_cache_segment(model_label, "default")
    return f"rag:{version}:{user_segment}:{model_segment}:{retrieval_digest}:{prompt_hash}"


def _load_cached_answer(key: str) -> dict[str, Any] | None:
    raw = _run_redis_command(lambda client: client.get(key))
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        LOGGER.debug("invalid JSON payload in cache for key %s", key, exc_info=True)
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _store_cached_answer(
    key: str,
    *,
    answer: RAGAnswer,
    validation: dict[str, Any] | None,
) -> None:
    payload = {
        "answer": answer.model_dump(mode="json"),
        "validation": validation,
        "model_name": answer.model_name,
        "cached_at": datetime.now(UTC).isoformat(),
    }
    try:
        serialised = json.dumps(payload)
    except TypeError:
        LOGGER.debug("failed to serialise cache payload", exc_info=True)
        return
    _run_redis_command(lambda client: client.set(key, serialised, ex=_CACHE_TTL_SECONDS))


def _format_anchor(passage: HybridSearchResult | Passage) -> str:
    if getattr(passage, "page_no", None) is not None:
        return f"page {passage.page_no}"
    if getattr(passage, "t_start", None) is not None:
        t_end = getattr(passage, "t_end", None)
        if t_end is None:
            return f"t={passage.t_start:.0f}s"
        return f"t={passage.t_start:.0f}-{t_end:.0f}s"
    return "context"


def _build_citations(results: Sequence[HybridSearchResult]) -> list[RAGCitation]:
    citations: list[RAGCitation] = []
    for index, result in enumerate(results, start=1):
        if not result.osis_ref:
            continue
        anchor = _format_anchor(result)
        snippet = (result.snippet or result.text).strip()
        citations.append(
            RAGCitation(
                index=index,
                osis=result.osis_ref,
                anchor=anchor,
                passage_id=result.id,
                document_id=result.document_id,
                document_title=result.document_title,
                snippet=snippet,
            )
        )
    return citations


def _build_retrieval_digest(results: Sequence[HybridSearchResult]) -> str:
    digest = hashlib.sha256()
    for result in results:
        digest.update(str(result.id).encode("utf-8"))
        digest.update(str(result.document_id).encode("utf-8"))
        digest.update(str(result.osis_ref or "").encode("utf-8"))
        digest.update(str(result.rank).encode("utf-8"))
        digest.update(str(result.snippet or result.text or "").encode("utf-8"))
        digest.update(_format_anchor(result).encode("utf-8"))
    return digest.hexdigest()


def _validate_model_completion(
    completion: str,
    citations: Sequence[RAGCitation],
) -> dict[str, Any]:
    if not completion or not completion.strip():
        raise GuardrailError("Model completion was empty")

    marker_index = completion.lower().rfind("sources:")
    if marker_index == -1:
        raise GuardrailError("Model completion missing 'Sources:' line")

    sources_text = completion[marker_index + len("Sources:") :].strip()
    if not sources_text:
        raise GuardrailError("Model completion missing citations after 'Sources:'")

    entries = [entry.strip() for entry in re.split(r";|\n", sources_text) if entry.strip()]
    if not entries:
        raise GuardrailError("Model completion missing citations after 'Sources:'")

    expected = {citation.index: citation for citation in citations}
    mismatches: list[str] = []
    parsed_entries: list[dict[str, Any]] = []
    cited_indices: list[int] = []

    for entry in entries:
        entry_match = _CITATION_ENTRY_PATTERN.match(entry)
        if not entry_match:
            mismatches.append(f"unparseable citation '{entry}'")
            continue

        index = int(entry_match.group("index"))
        osis = entry_match.group("osis").strip()
        anchor = entry_match.group("anchor").strip()
        parsed_entries.append({"index": index, "osis": osis, "anchor": anchor})
        cited_indices.append(index)

        citation = expected.get(index)
        if citation is None:
            mismatches.append(
                f"citation index {index} not present in retrieved passages"
            )
            continue
        if osis != citation.osis:
            mismatches.append(
                f"citation [{index}] OSIS mismatch (expected {citation.osis}, got {osis})"
            )
        if anchor != citation.anchor:
            mismatches.append(
                f"citation [{index}] anchor mismatch (expected {citation.anchor}, got {anchor})"
            )

    if not cited_indices:
        raise GuardrailError("Model completion did not include any recognised citations")

    if mismatches:
        raise GuardrailError(
            "Model citations failed guardrails: " + "; ".join(mismatches)
        )

    return {
        "status": "passed",
        "cited_indices": sorted(set(cited_indices)),
        "citation_count": len(parsed_entries),
        "sources": parsed_entries,
    }


def _guarded_answer(
    session: Session,
    *,
    question: str | None,
    results: Sequence[HybridSearchResult],
    registry: LLMRegistry,
    model_hint: str | None = None,
    recorder: "TrailRecorder | None" = None,
) -> RAGAnswer:
    citations = _build_citations(results)
    if not citations:
        raise GuardrailError(
            "Retrieved passages lacked OSIS references; aborting generation"
        )

    summary_lines = []
    for citation, result in zip(citations, results):
        summary_lines.append(
            f"[{citation.index}] {citation.snippet} — {citation.document_title or citation.document_id}"
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
    if recorder and getattr(recorder, "trail", None) is not None:
        user_id = getattr(recorder.trail, "user_id", None)

    router = get_router(session, registry=registry)
    candidates = list(router.iter_candidates("rag", model_hint))
    if not candidates:
        raise GenerationError("No language models are available for workflow 'rag'")

    context_lines = [
        f"[{citation.index}] {citation.snippet} (OSIS {citation.osis}, {citation.anchor})"
        for citation in citations
    ]
    prompt_parts = [
        "You are Theo Engine's grounded assistant.",
        "Answer the question strictly from the provided passages.",
        "Cite evidence using the bracketed indices and retain OSIS + anchor in a Sources line.",
        "If the passages do not answer the question, state that explicitly.",
    ]
    if question:
        prompt_parts.append(f"Question: {question}")
    prompt_parts.append("Passages:")
    prompt_parts.extend(context_lines)
    prompt_parts.append("Respond with 2-3 sentences followed by 'Sources:'")
    prompt = "\\n".join(prompt_parts)

    retrieval_digest = _build_retrieval_digest(results)
    last_error: GenerationError | None = None
    selected_model: LLMModel | None = None

    cache_key = None
    cache_key_suffix = None
    cache_status = "skipped"

    for candidate in candidates:
        selected_model = candidate
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
                except GuardrailError as exc:
                    cache_status = "stale"
                    _run_redis_command(lambda client: client.delete(cache_key))
                    log_workflow_event(
                        "workflow.guardrails_cache",
                        workflow="rag",
                        status="stale",
                        cache_key_suffix=cache_key_suffix,
                    )
                    cache_event_logged = True
                    if recorder:
                        recorder.log_step(
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
                log_workflow_event(
                    "workflow.guardrails_cache",
                    workflow="rag",
                    status="stale",
                    cache_key_suffix=cache_key_suffix,
                )
            else:
                log_workflow_event(
                    "workflow.guardrails_cache",
                    workflow="rag",
                    status="miss",
                    cache_key_suffix=cache_key_suffix,
                )

        if recorder and cache_key:
            recorder.log_step(
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
            routed_generation = router.execute_generation(
                workflow="rag",
                model=candidate,
                prompt=prompt,
            )
        except GenerationError as exc:
            last_error = exc
            if recorder:
                recorder.log_step(
                    tool="llm.generate",
                    action="generate_grounded_answer",
                    status="failed",
                    input_payload=llm_payload,
                    output_digest=str(exc),
                    error_message=str(exc),
                )
            continue

        completion = routed_generation.output
        if recorder:
            recorder.log_step(
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
            completion = completion.strip() + f"\\n\\nSources: {sources_line}"
        try:
            validation_result = _validate_model_completion(completion, citations)
        except GuardrailError as exc:
            log_workflow_event(
                "workflow.guardrails_validation",
                workflow="rag",
                status="failed",
                cache_status=cache_status,
                cache_key_suffix=cache_key_suffix,
            )
            if recorder:
                recorder.log_step(
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
            raise
        model_output = completion
        model_name = candidate.name
        if cache_status == "stale":
            cache_status = "refresh"
        break

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
        if recorder:
            recorder.log_step(
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
    )

    if cache_key and model_output and validation_result and cache_status in {
        "miss",
        "refresh",
    }:
        _store_cached_answer(cache_key, answer=answer, validation=validation_result)
        if cache_status == "refresh":
            log_workflow_event(
                "workflow.guardrails_cache",
                workflow="rag",
                status="refresh",
                cache_key_suffix=cache_key_suffix,
            )

    if recorder:
        recorder.log_step(
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

    return answer


def _search(
    session: Session,
    *,
    query: str | None,
    osis: str | None,
    filters: HybridSearchFilters,
    k: int = 8,
) -> list[HybridSearchResult]:
    request = HybridSearchRequest(query=query, osis=osis, filters=filters, k=k)
    return hybrid_search(session, request)


def run_guarded_chat(
    session: Session,
    *,
    question: str,
    osis: str | None = None,
    filters: HybridSearchFilters | None = None,
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
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
        answer = _guarded_answer(
            session,
            question=question,
            results=results,
            registry=registry,
            model_hint=model_name,
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
        answer = _guarded_answer(
            session,
            question=question,
            results=results,
            registry=registry,
            model_hint=model_name,
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
        answer = _guarded_answer(
            session,
            question=query,
            results=results,
            registry=registry,
            model_hint=model_name,
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
        answer = _guarded_answer(
            session,
            question=f"How do {', '.join(participants)} interpret {osis}?",
            results=results,
            registry=registry,
            model_hint=model_name,
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
        registry = get_llm_registry(session)
        answer = _guarded_answer(
            session,
            question="What are the key audio/video insights?",
            results=results,
            registry=registry,
            model_hint=model_name,
        )
        set_span_attribute(span, "workflow.citation_count", len(answer.citations))
        highlights = [
            f"{citation.document_title or citation.document_id}: {citation.snippet}"
            for citation in answer.citations
        ]
        return MultimediaDigestResponse(
            collection=collection, highlights=highlights, answer=answer
        )


def generate_devotional_flow(
    session: Session,
    *,
    osis: str,
    focus: str,
    model_name: str | None = None,
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
        registry = get_llm_registry(session)
        answer = _guarded_answer(
            session,
            question=f"Devotional focus: {focus}",
            results=results,
            registry=registry,
            model_hint=model_name,
        )
        set_span_attribute(span, "workflow.citation_count", len(answer.citations))
        log_workflow_event(
            "workflow.answer_composed",
            workflow="devotional",
            citations=len(answer.citations),
        )
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
        registry = get_llm_registry(session)
        answer = _guarded_answer(
            session,
            question=f"Reconcile viewpoints for {osis} in {thread}",
            results=results,
            registry=registry,
            model_hint=model_name,
        )
        set_span_attribute(span, "workflow.citation_count", len(answer.citations))
        log_workflow_event(
            "workflow.answer_composed",
            workflow="research_reconciliation",
            citations=len(answer.citations),
        )
        synthesis_lines = [
            f"{citation.osis}: {citation.snippet}" for citation in answer.citations
        ]
        synthesized_view = "\n".join(synthesis_lines)
        return CollaborationResponse(
            thread=thread, synthesized_view=synthesized_view, answer=answer
        )


_SUPPORTED_DELIVERABLE_FORMATS = {"markdown", "ndjson", "csv"}


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
        f"export_id: {manifest.export_id}",
        f"schema_version: {manifest.schema_version}",
        f"generated_at: {manifest.generated_at.isoformat()}",
        f"type: {manifest.type}",
    ]
    if manifest.model_preset:
        lines.append(f"model_preset: {manifest.model_preset}")
    if manifest.git_sha:
        lines.append(f"git_sha: {manifest.git_sha}")
    if manifest.sources:
        lines.append(f"sources: {json.dumps(manifest.sources)}")
    if manifest.filters:
        lines.append(f"filters: {json.dumps(manifest.filters, sort_keys=True)}")
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


def _render_sermon_markdown(
    manifest: DeliverableManifest, response: SermonPrepResponse
) -> str:
    lines = _manifest_front_matter(manifest)
    lines.append(f"# Sermon Prep — {response.topic}")
    if response.osis:
        lines.append(f"Focus Passage: {response.osis}\n")
    if response.outline:
        lines.append("## Outline")
        for item in response.outline:
            lines.append(f"- {item}")
        lines.append("")
    if response.key_points:
        lines.append("## Key Points")
        for point in response.key_points:
            lines.append(f"- {point}")
        lines.append("")
    if response.answer.citations:
        lines.append("## Citations")
        for citation in response.answer.citations:
            lines.append(
                f"- {citation.osis} ({citation.anchor}) — {citation.snippet}"
            )
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
    lines.append(f"# Q&A Transcript — {title or manifest.filters.get('document_id')}")
    for row in rows:
        anchor = row.get("osis") or row.get("page_no") or row.get("t_start")
        lines.append(
            f"- **{row['speaker']}** ({anchor}): {row['text']}"
        )
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


def build_transcript_deliverable(
    session: Session,
    document_id: str,
    *,
    formats: Sequence[str],
) -> DeliverablePackage:
    """Generate transcript exports for the requested document."""

    document = session.get(Document, document_id)
    if document is None:
        raise GuardrailError(f"Document {document_id} not found")
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
) -> tuple[str, str]:
    normalised = format.lower()
    package = build_sermon_deliverable(response, formats=[normalised])
    asset = package.get_asset(normalised)
    return asset.content, asset.media_type


def build_transcript_package(
    session: Session,
    document_id: str,
    *,
    format: str,
) -> tuple[str, str]:
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
    "MultimediaDigestResponse",
    "RAGAnswer",
    "RAGCitation",
    "SermonPrepResponse",
    "VerseCopilotResponse",
    "build_sermon_deliverable",
    "build_sermon_prep_package",
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
