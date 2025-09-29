"""Guardrailed RAG workflows for Theo Engine."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
import textwrap
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Literal,
    Mapping,
    Pattern,
    Sequence,
    TypeVar,
)
from urllib.parse import urlencode

try:  # pragma: no cover - optional dependency guard
    from redis import asyncio as redis_asyncio
except ImportError:  # pragma: no cover - redis is optional at runtime
    redis_asyncio = None  # type: ignore[assignment]

from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..core.version import get_git_sha
from ..db.models import Document, Passage
from ..export.formatters import SCHEMA_VERSION, generate_export_id
from pydantic import Field

from ..models.base import APIModel
from ..models.export import DeliverableAsset, DeliverableManifest, DeliverablePackage
from ..models.search import HybridSearchFilters, HybridSearchRequest, HybridSearchResult
from ..retriever.hybrid import hybrid_search
from ..telemetry import (
    RAG_CACHE_EVENTS,
    instrument_workflow,
    log_workflow_event,
    set_span_attribute,
)
from .clients import GenerationError
from .registry import LLMModel, LLMRegistry, get_llm_registry
from .router import get_router

if TYPE_CHECKING:  # pragma: no cover - hints only
    from .trails import TrailRecorder


LOGGER = logging.getLogger(__name__)

_RAG_TRACER = trace.get_tracer("theo.rag")

_CACHE_TTL_SECONDS = 30 * 60
_CITATION_ENTRY_PATTERN = re.compile(r"^\[(?P<index>\d+)]\s*(?P<osis>[^()]+?)\s*\((?P<anchor>[^()]+)\)$")
_SENTENCE_PATTERN = re.compile(r"[^.!?]*[.!?]|[^.!?]+$")
_MARKDOWN_ESCAPE_PATTERN = re.compile(r"([\\`*_{}\[\]()#+.!|\-])")

_ADVERSARIAL_REPLACEMENTS: tuple[tuple[Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:ignore|disregard|forget)\b[^\n]{0,40}?\b(?:previous|prior|all)\s+instructions?\b",
            re.IGNORECASE,
        ),
        "[filtered-instruction]",
    ),
    (
        re.compile(
            r"\b(?:override|reset|disable)\b[^\n]{0,40}?\b(?:guardrails?|safety|system)\b",
            re.IGNORECASE,
        ),
        "[filtered-override]",
    ),
    (
        re.compile(r"drop\s+table\b", re.IGNORECASE),
        "[filtered-sql]",
    ),
    (
        re.compile(r"<\s*/?script\b[^>]*>", re.IGNORECASE),
        "[filtered-html]",
    ),
    (
        re.compile(r"<\s*/?style\b[^>]*>", re.IGNORECASE),
        "[filtered-html]",
    ),
    (
        re.compile(r"<!--.*?-->", re.DOTALL),
        "[filtered-comment]",
    ),
    (
        re.compile(r"```(?:html|javascript|sql)[\s\S]*?```", re.IGNORECASE),
        "[filtered-code-block]",
    ),
)

_DISALLOWED_COMPLETION_PATTERNS: tuple[tuple[Pattern[str], str], ...] = (
    (
        re.compile(r"\bselect\b[^\n]+\bfrom\b", re.IGNORECASE),
        "SQL SELECT pattern",
    ),
    (
        re.compile(
            r"\b(insert|update|delete|drop|alter|create)\b[^\n]+\btable\b",
            re.IGNORECASE,
        ),
        "SQL modification pattern",
    ),
    (
        re.compile(r"<\s*/?script\b", re.IGNORECASE),
        "script markup",
    ),
    (
        re.compile(r"password\s*[:=]", re.IGNORECASE),
        "credential disclosure",
    ),
    (
        re.compile(r"api[-_\s]*key", re.IGNORECASE),
        "credential disclosure",
    ),
    (
        re.compile(r"access\s*token", re.IGNORECASE),
        "credential disclosure",
    ),
    (
        re.compile(r"secret\s*(?:key|token)", re.IGNORECASE),
        "credential disclosure",
    ),
)

_redis_client: Any = None


def _normalise_profile_value(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().lower()
    return text or None


def _escape_markdown_html(value: str) -> str:
    if not value:
        return ""
    escaped = (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return _MARKDOWN_ESCAPE_PATTERN.sub(r"\\\1", escaped)


def _sanitize_markdown_field(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return _escape_markdown_html(text)


def _scrub_adversarial_language(value: str | None) -> str | None:
    if not value:
        return value
    text = value
    for pattern, replacement in _ADVERSARIAL_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def _sanitize_json_structure(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _sanitize_json_structure(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple, set)):
        return [_sanitize_json_structure(item) for item in payload]
    if isinstance(payload, str):
        return _sanitize_markdown_field(payload)
    return payload


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
    ordered = list(results)
    if not filters:
        return ordered, None

    tradition_filter = _normalise_profile_value(filters.theological_tradition)
    domain_filter = _normalise_profile_value(filters.topic_domain)
    if not tradition_filter and not domain_filter:
        payload = {
            key: value
            for key, value in {
                "theological_tradition": filters.theological_tradition,
                "topic_domain": filters.topic_domain,
            }.items()
            if value
        }
        return ordered, payload or None

    matched: list[HybridSearchResult] = []
    remainder: list[HybridSearchResult] = []
    for result in ordered:
        meta = getattr(result, "meta", None)
        meta_mapping: Mapping[str, Any] | None = meta if isinstance(meta, Mapping) else None
        meta_tradition = (
            _normalise_profile_value(str(meta_mapping.get("theological_tradition")))
            if meta_mapping and meta_mapping.get("theological_tradition") is not None
            else None
        )
        domains = _extract_topic_domains(meta_mapping)

        matches_tradition = True
        if tradition_filter:
            matches_tradition = meta_tradition == tradition_filter

        matches_domain = True
        if domain_filter:
            matches_domain = domain_filter in domains

        if matches_tradition and matches_domain:
            matched.append(result)
        else:
            remainder.append(result)

    if not matched:
        LOGGER.warning(
            "guardrail profile rejected retrieved passages",
            extra={
                "theological_tradition": filters.theological_tradition,
                "topic_domain": filters.topic_domain,
            },
        )
        raise GuardrailError("No passages matched the requested guardrail profile")

    payload = {
        key: value
        for key, value in {
            "theological_tradition": filters.theological_tradition,
            "topic_domain": filters.topic_domain,
        }.items()
        if value
    }
    return matched + remainder, payload or None


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
    source_url: str | None = None
    raw_snippet: str | None = Field(default=None, exclude=True)


class RAGAnswer(APIModel):
    summary: str
    citations: list[RAGCitation]
    model_name: str | None = None
    model_output: str | None = None
    guardrail_profile: dict[str, str] | None = None


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


def _build_source_url(result: HybridSearchResult) -> str:
    params: dict[str, str] = {}
    if getattr(result, "page_no", None) is not None:
        params["page"] = str(result.page_no)
    t_start = getattr(result, "t_start", None)
    if t_start is not None:
        params["t"] = str(math.floor(t_start))
    query = urlencode(params)
    base = f"/doc/{result.document_id}"
    anchor = f"#passage-{result.id}"
    return f"{base}?{query}{anchor}" if query else f"{base}{anchor}"


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
    citations: list[RAGCitation] = []
    for index, result in enumerate(results, start=1):
        if not result.osis_ref:
            continue
        anchor = _format_anchor(result)
        snippet = _derive_snippet(result)
        raw_snippet = None
        raw_text = getattr(result, "raw_text", None)
        if raw_text:
            raw_snippet = _derive_snippet(
                result, text=raw_text, fallback=raw_text
            )
        citations.append(
            RAGCitation(
                index=index,
                osis=result.osis_ref,
                anchor=anchor,
                passage_id=result.id,
                document_id=result.document_id,
                document_title=result.document_title,
                snippet=snippet,
                source_url=_build_source_url(result),
                raw_snippet=raw_snippet,
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


def ensure_completion_safe(completion: str | None) -> None:
    if not completion:
        return
    for pattern, reason in _DISALLOWED_COMPLETION_PATTERNS:
        if pattern.search(completion):
            raise GuardrailError(
                f"Model completion failed safety check: {reason}"
            )


def _guarded_answer(
    session: Session,
    *,
    question: str | None,
    results: Sequence[HybridSearchResult],
    registry: LLMRegistry,
    model_hint: str | None = None,
    recorder: "TrailRecorder | None" = None,
    filters: HybridSearchFilters | None = None,
) -> RAGAnswer:
    ordered_results, guardrail_profile = _apply_guardrail_profile(results, filters)
    citations = _build_citations(ordered_results)
    if not citations:
        raise GuardrailError(
            "Retrieved passages lacked OSIS references; aborting generation"
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
    if recorder and getattr(recorder, "trail", None) is not None:
        user_id = getattr(recorder.trail, "user_id", None)

    router = get_router(session, registry=registry)
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
    sanitized_question = _scrub_adversarial_language(question)
    if sanitized_question:
        prompt_parts.append(f"Question: {sanitized_question}")
    prompt_parts.append("Passages:")
    prompt_parts.extend(context_lines)
    prompt_parts.append("Respond with 2-3 sentences followed by 'Sources:'")
    prompt = "\\n".join(prompt_parts)

    retrieval_digest = _build_retrieval_digest(ordered_results)
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
                    ensure_completion_safe(cache_hit_payload.model_output)
                except GuardrailError as exc:
                    cache_status = "stale"
                    _run_redis_command(lambda client: client.delete(cache_key))
                    RAG_CACHE_EVENTS.labels(status="stale").inc()
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
                span.set_attribute("rag.completion_tokens", max(len(routed_generation.output) // 4, 0) if routed_generation.output else 0)

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
            filters=filters,
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
            filters=filters,
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
            filters=filters,
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
            filters=filters,
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
        answer = _guarded_answer(
            session,
            question="What are the key audio/video insights?",
            results=results,
            registry=registry,
            model_hint=model_name,
            recorder=recorder,
            filters=filters,
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
        answer = _guarded_answer(
            session,
            question=f"Devotional focus: {focus}",
            results=results,
            registry=registry,
            model_hint=model_name,
            recorder=recorder,
            filters=filters,
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
        answer = _guarded_answer(
            session,
            question=f"Reconcile viewpoints for {osis} in {thread}",
            results=results,
            registry=registry,
            model_hint=model_name,
            recorder=recorder,
            filters=filters,
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
