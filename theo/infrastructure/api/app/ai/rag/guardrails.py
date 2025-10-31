"""Guardrail utilities for RAG workflows."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Any, Iterable, Mapping, Pattern, Sequence
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.application.ports.ai_registry import GenerationError
from theo.infrastructure.api.app.persistence_models import Document, Passage

from ...models.search import HybridSearchFilters, HybridSearchResult
from .models import RAGAnswer, RAGCitation
from .prompts import sanitise_json_structure

LOGGER = logging.getLogger(__name__)

_CITATION_ENTRY_PATTERN = re.compile(
    r"^\[(?P<index>\d+)]\s*(?P<osis>[^()]+?)\s*\((?P<anchor>[^()]+)\)$"
)
_SENTENCE_PATTERN = re.compile(r"[^.!?]*[.!?]|[^.!?]+$")

_DISALLOWED_COMPLETION_PATTERNS: tuple[tuple[Pattern[str], str], ...] = (
    # SQL injection patterns
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
        re.compile(r";\s*(drop|delete|truncate)\b", re.IGNORECASE),
        "SQL statement chaining",
    ),
    # XSS and script injection
    (re.compile(r"<\s*/?script\b", re.IGNORECASE), "script markup"),
    (re.compile(r"<\s*/?iframe\b", re.IGNORECASE), "iframe markup"),
    (re.compile(r"javascript\s*:", re.IGNORECASE), "javascript protocol"),
    (re.compile(r"on\w+\s*=\s*[\"']", re.IGNORECASE), "inline event handler"),
    # Credential leakage
    (
        re.compile(r"password\s*(?:[:=]|is\b)", re.IGNORECASE),
        "credential disclosure",
    ),
    (re.compile(r"api[-_\s]*key\s*[:=]", re.IGNORECASE), "credential disclosure"),
    (
        re.compile(r"access(?:[-_\s]*token)\s*[:=]", re.IGNORECASE),
        "credential disclosure",
    ),
    (re.compile(r"secret\s*(?:key|token)\s*[:=]", re.IGNORECASE), "credential disclosure"),
    (re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE), "bearer token"),
    # Command injection
    (re.compile(r"\$\(.*\)", re.IGNORECASE), "command substitution"),
    (re.compile(r"`.*`"), "backtick command execution"),
    (re.compile(r"&&|;|\||>\s*/", re.IGNORECASE), "shell metacharacters"),
    # Path traversal
    (re.compile(r"\.\./", re.IGNORECASE), "path traversal"),
    (re.compile(r"\.\.\\", re.IGNORECASE), "path traversal (Windows)"),
    # Prompt injection patterns
    (re.compile(r"ignore\s+(previous|all)\s+instructions?", re.IGNORECASE), "prompt override"),
    (re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE), "system prompt injection"),
    (re.compile(r"</\s*context\s*>", re.IGNORECASE), "context escape"),
)


class GuardrailError(GenerationError):
    """Raised when an answer violates grounding requirements."""

    def __init__(
        self,
        message: str,
        *,
        safe_refusal: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.safe_refusal = safe_refusal
        self.metadata = metadata or {}


def _normalise_profile_value(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().lower()
    return text or None


def _extract_topic_domains(meta: Mapping[str, Any] | None) -> set[str]:
    domains: set[str] = set()
    if not meta:
        return domains
    raw = meta.get("topic_domains") or meta.get("topic_domain")
    if raw is None:
        return domains
    if isinstance(raw, str):
        candidates: Iterable[str] = re.split(r"[,;]", raw)
    elif isinstance(raw, Iterable):
        candidates = raw
    else:
        return domains
    for item in candidates:
        text = str(item).strip().lower()
        if text:
            domains.add(text)
    return domains


def apply_guardrail_profile(
    results: Sequence[HybridSearchResult],
    filters: HybridSearchFilters | None,
) -> tuple[list[HybridSearchResult], dict[str, str] | None]:
    ordered = list(results)
    if not filters:
        LOGGER.debug(
            "guardrail profile bypassed - no filters provided",
            extra={
                "total_results": len(ordered),
                "filters_applied": False,
            },
        )
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
        LOGGER.debug(
            "guardrail profile bypassed - no valid filter values",
            extra={
                "total_results": len(ordered),
                "filters_applied": False,
                "raw_tradition_filter": filters.theological_tradition,
                "raw_domain_filter": filters.topic_domain,
            },
        )
        return ordered, payload or None

    # Enhanced telemetry: log filtering start state
    LOGGER.info(
        "guardrail profile filtering started",
        extra={
            "total_results": len(ordered),
            "filters_applied": True,
            "tradition_filter": tradition_filter,
            "domain_filter": domain_filter,
            "passage_ids_sample": [result.id for result in ordered[:3]],
            "total_passage_count": len(ordered),
        },
    )

    matched: list[HybridSearchResult] = []
    remainder: list[HybridSearchResult] = []
    missing_metadata_count = 0
    tradition_mismatch_count = 0
    domain_mismatch_count = 0
    
    for result in ordered:
        meta = getattr(result, "meta", None)
        meta_mapping: Mapping[str, Any] | None = meta if isinstance(meta, Mapping) else None
        
        # Track missing metadata
        if not meta_mapping:
            missing_metadata_count += 1
            remainder.append(result)
            continue
            
        meta_tradition = (
            _normalise_profile_value(str(meta_mapping.get("theological_tradition")))
            if meta_mapping and meta_mapping.get("theological_tradition") is not None
            else None
        )
        domains = _extract_topic_domains(meta_mapping)

        matches_tradition = True
        if tradition_filter:
            matches_tradition = meta_tradition == tradition_filter
            if not matches_tradition:
                tradition_mismatch_count += 1

        matches_domain = True
        if domain_filter:
            matches_domain = domain_filter in domains
            if not matches_domain:
                domain_mismatch_count += 1

        if matches_tradition and matches_domain:
            matched.append(result)
        else:
            remainder.append(result)

    # Enhanced telemetry: log filtering results
    match_percentage = (len(matched) / len(ordered) * 100) if ordered else 0
    LOGGER.info(
        "guardrail profile filtering completed",
        extra={
            "total_results": len(ordered),
            "matched_count": len(matched),
            "remainder_count": len(remainder),
            "match_percentage": round(match_percentage, 1),
            "missing_metadata_count": missing_metadata_count,
            "tradition_mismatch_count": tradition_mismatch_count,
            "domain_mismatch_count": domain_mismatch_count,
            "tradition_filter": tradition_filter,
            "domain_filter": domain_filter,
        },
    )
    
    # Debug-level detailed passage tracking
    LOGGER.debug(
        "guardrail profile filtering detailed results",
        extra={
            "matched_passage_ids": [result.id for result in matched],
            "remainder_passage_ids": [result.id for result in remainder],
        },
    )

    if not matched:
        LOGGER.warning(
            "guardrail profile rejected retrieved passages - no matches found",
            extra={
                "total_results": len(ordered),
                "matched_count": 0,
                "match_percentage": 0.0,
                "missing_metadata_count": missing_metadata_count,
                "tradition_mismatch_count": tradition_mismatch_count,
                "domain_mismatch_count": domain_mismatch_count,
                "theological_tradition": filters.theological_tradition,
                "topic_domain": filters.topic_domain,
                "passage_ids_sample": [result.id for result in ordered[:3]],
                "total_passage_count": len(ordered),
            },
        )
        raise GuardrailError(
            "No passages matched the requested guardrail profile",
            safe_refusal=True,
            metadata={
                "code": "guardrail_profile_no_match",
                "guardrail": "retrieval",
                "suggested_action": "search",
                "total_results": len(ordered),
                "matched_count": 0,
                "match_percentage": 0.0,
                "missing_metadata_count": missing_metadata_count,
                "tradition_mismatch_count": tradition_mismatch_count,
                "domain_mismatch_count": domain_mismatch_count,
                "theological_tradition": filters.theological_tradition,
                "topic_domain": filters.topic_domain,
                "passage_ids_sample": [result.id for result in ordered[:3]],
                "total_passage_count": len(ordered),
            },
        )

    payload = {
        key: value
        for key, value in {
            "theological_tradition": filters.theological_tradition,
            "topic_domain": filters.topic_domain,
        }.items()
        if value
    }
    
    # Enhanced telemetry: log successful filtering
    LOGGER.info(
        "guardrail profile filtering successful",
        extra={
            "total_results": len(ordered),
            "matched_count": len(matched),
            "remainder_count": len(remainder),
            "match_percentage": round(match_percentage, 1),
            "tradition_filter": tradition_filter,
            "domain_filter": domain_filter,
            "payload": payload,
        },
    )
    
    return matched + remainder, payload or None


def _format_anchor(passage: HybridSearchResult | Passage) -> str:
    if getattr(passage, "page_no", None) is not None:
        return f"page {passage.page_no}"
    if getattr(passage, "t_start", None) is not None:
        t_end = getattr(passage, "t_end", None)
        if t_end is None:
            return f"t={passage.t_start:.0f}s"
        return f"t={passage.t_start:.0f}-{t_end:.0f}s"
    return "context"


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


def build_citations(results: Sequence[HybridSearchResult]) -> list[RAGCitation]:
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


def build_guardrail_result(passage: Passage, document: Document | None) -> HybridSearchResult:
    snippet_source = passage.text or document.title or "Guardrail passage"
    snippet = _normalise_snippet(snippet_source)
    title = document.title if document else None

    return HybridSearchResult(
        id=passage.id,
        document_id=passage.document_id,
        text=passage.text,
        raw_text=passage.raw_text,
        osis_ref=passage.osis_ref,
        start_char=passage.start_char,
        end_char=passage.end_char,
        page_no=passage.page_no,
        t_start=passage.t_start,
        t_end=passage.t_end,
        score=1.0,
        meta={},
        document_title=title,
        snippet=snippet,
        rank=0,
        highlights=None,
    )


def _normalise_snippet(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= 240:
        return collapsed
    return collapsed[:237].rstrip() + "…"


def load_guardrail_reference(session: Session) -> HybridSearchResult | None:
    preferred_ids = ("redteam-passage", "guardrail-reference")
    for passage_id in preferred_ids:
        passage = session.get(Passage, passage_id)
        if passage and passage.osis_ref:
            document = session.get(Document, passage.document_id)
            return build_guardrail_result(passage, document)

    row = (
        session.execute(
            select(Passage, Document)
            .join(Document)
            .where(Passage.osis_ref.isnot(None))
            .limit(1)
        )
        .first()
    )
    if not row:
        return None
    passage, document = row
    if not passage.osis_ref:
        return None
    return build_guardrail_result(passage, document)


def load_passages_for_osis(
    session: Session, osis: str, *, limit: int = 3
) -> list[HybridSearchResult]:
    passages = (
        session.execute(
            select(Passage).where(Passage.osis_ref == osis).limit(limit)
        )
        .scalars()
        .all()
    )
    results: list[HybridSearchResult] = []
    for passage in passages:
        document = session.get(Document, passage.document_id)
        results.append(build_guardrail_result(passage, document))
    return results


def build_retrieval_digest(results: Sequence[HybridSearchResult]) -> str:
    digest = hashlib.sha256()
    for result in results:
        digest.update(str(result.id).encode("utf-8"))
        digest.update(str(result.document_id).encode("utf-8"))
        digest.update(str(result.osis_ref or "").encode("utf-8"))
        digest.update(str(result.rank).encode("utf-8"))
        digest.update(str(result.snippet or result.text or "").encode("utf-8"))
        digest.update(_format_anchor(result).encode("utf-8"))
    return digest.hexdigest()


def _normalise_citation_value(value: str) -> str:
    """Normalize citation values for robust comparison."""
    if not value:
        return ""
    # Remove surrounding punctuation but preserve internal structure
    normalized = re.sub(r"^[^\w\d.]+|[^\w\d.]+$", "", value.strip())
    # Normalize multiple spaces to single space, but preserve dots in OSIS refs
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.lower()


def validate_model_completion(
    completion: str,
    citations: Sequence[RAGCitation],
) -> dict[str, Any]:
    """Validate model completion and return structured decision reasons."""
    
    if not completion or not completion.strip():
        return {
            "status": "failed",
            "decision_reason": "empty_completion",
            "decision_message": "Model completion was empty",
            "suggested_action": "search",
            "cited_indices": [],
            "citation_count": 0,
            "sources": [],
        }

    # Check for extra text before Sources line
    sources_marker_match = re.search(r"sources:\s*$", completion, re.IGNORECASE | re.MULTILINE)
    if not sources_marker_match:
        return {
            "status": "failed",
            "decision_reason": "missing_sources_line",
            "decision_message": "Model completion missing 'Sources:' line",
            "suggested_action": "search",
            "cited_indices": [],
            "citation_count": 0,
            "sources": [],
        }

    # Verify Sources line is near the end (allow trailing whitespace/newlines)
    sources_line_index = sources_marker_match.start()
    content_after_sources = completion[sources_line_index + len(sources_marker_match.group(0)):].strip()
    if content_after_sources and not re.match(r"^\s*(?:\[\d+\]|Here are|Sources:)", content_after_sources, re.IGNORECASE):
        return {
            "status": "failed",
            "decision_reason": "extra_content_after_sources",
            "decision_message": "Extra content found after 'Sources:' line before citations",
            "suggested_action": "search",
            "cited_indices": [],
            "citation_count": 0,
            "sources": [],
        }

    marker_index = completion.lower().rfind("sources:")
    sources_text = completion[marker_index + len("Sources:"):].strip()
    if not sources_text:
        return {
            "status": "failed",
            "decision_reason": "missing_citations",
            "decision_message": "Model completion missing citations after 'Sources:'",
            "suggested_action": "search",
            "cited_indices": [],
            "citation_count": 0,
            "sources": [],
        }

    entries = [entry.strip() for entry in re.split(r";|\n", sources_text) if entry.strip()]
    if not entries:
        return {
            "status": "failed",
            "decision_reason": "missing_citations",
            "decision_message": "Model completion missing citations after 'Sources:'",
            "suggested_action": "search",
            "cited_indices": [],
            "citation_count": 0,
            "sources": [],
        }

    expected = {citation.index: citation for citation in citations}
    mismatches: list[str] = []
    parsed_entries: list[dict[str, Any]] = []
    cited_indices: list[int] = []

    for entry in entries:
        entry_match = _CITATION_ENTRY_PATTERN.match(entry)
        if not entry_match:
            mismatches.append(f"citation '{entry}' is unparsable")
            continue

        index = int(entry_match.group("index"))
        osis = entry_match.group("osis").strip()
        anchor = entry_match.group("anchor").strip()
        
        # Normalize values for comparison
        normalized_osis = _normalise_citation_value(osis)
        normalized_anchor = _normalise_citation_value(anchor)
        
        parsed_entries.append({"index": index, "osis": osis, "anchor": anchor})
        cited_indices.append(index)

        # Check for duplicate indices
        if cited_indices.count(index) > 1:
            mismatches.append(f"duplicate citation index {index}")
            continue

        citation = expected.get(index)
        if citation is None:
            mismatches.append(
                f"citation index {index} not present in retrieved passages"
            )
            continue
            
        # Compare normalized values
        expected_osis = _normalise_citation_value(citation.osis)
        expected_anchor = _normalise_citation_value(citation.anchor)
        
        if normalized_osis != expected_osis:
            mismatches.append(
                f"citation [{index}] OSIS mismatch (expected '{citation.osis}', got '{osis}')"
            )
        if normalized_anchor != expected_anchor:
            mismatches.append(
                f"citation [{index}] anchor mismatch (expected '{citation.anchor}', got '{anchor}')"
            )

    if not cited_indices:
        return {
            "status": "failed",
            "decision_reason": "unrecognised_citations",
            "decision_message": "Model completion did not include any recognised citations",
            "suggested_action": "search",
            "cited_indices": [],
            "citation_count": 0,
            "sources": [],
        }

    # Check minimum coverage - require at least 1 citation or 50% of available (max 3)
    min_required = min(max(1, len(citations) // 2), 3)
    unique_cited = len(set(cited_indices))
    if unique_cited < min_required:
        mismatches.append(
            f"insufficient citation coverage (cited {unique_cited}, required at least {min_required})"
        )

    if mismatches:
        return {
            "status": "failed",
            "decision_reason": "citation_mismatch",
            "decision_message": "Model citations failed guardrails: " + "; ".join(mismatches),
            "suggested_action": "search",
            "cited_indices": sorted(set(cited_indices)),
            "citation_count": len(parsed_entries),
            "sources": parsed_entries,
            "validation_details": {
                "mismatches": mismatches,
                "unique_cited": unique_cited,
                "min_required": min_required,
                "total_available": len(citations),
            },
        }

    return {
        "status": "passed",
        "decision_reason": "validation_successful",
        "decision_message": "All guardrails passed successfully",
        "suggested_action": None,
        "cited_indices": sorted(set(cited_indices)),
        "citation_count": len(parsed_entries),
        "sources": parsed_entries,
        "validation_details": {
            "unique_cited": unique_cited,
            "min_required": min_required,
            "total_available": len(citations),
        },
    }


def validate_model_completion_strict(
    completion: str,
    citations: Sequence[RAGCitation],
) -> dict[str, Any]:
    """Validate model completion and raise GuardrailError on failure for backward compatibility."""
    result = validate_model_completion(completion, citations)
    if result["status"] == "failed":
        raise GuardrailError(
            result["decision_message"],
            metadata={
                "code": f"generation_{result['decision_reason']}",
                "guardrail": "generation",
                "suggested_action": result["suggested_action"],
                "reason": result["decision_message"],
                "validation_details": result.get("validation_details"),
            },
        )
    return result


def ensure_completion_safe(completion: str | None) -> None:
    if not completion:
        return
    for pattern, reason in _DISALLOWED_COMPLETION_PATTERNS:
        if pattern.search(completion):
            raise GuardrailError(
                f"Model completion failed safety check: {reason}",
                metadata={
                    "code": "safety_pattern_detected",
                    "guardrail": "safety",
                    "suggested_action": "search",
                    "reason": reason,
                },
            )


def guardrail_metadata(answer: RAGAnswer) -> dict[str, Any]:
    payload = {
        "summary": answer.summary,
        "citations": [citation.model_dump(mode="json") for citation in answer.citations],
    }
    return sanitise_json_structure(payload)


__all__ = [
    "GuardrailError",
    "apply_guardrail_profile",
    "build_citations",
    "build_guardrail_result",
    "build_retrieval_digest",
    "ensure_completion_safe",
    "guardrail_metadata",
    "load_guardrail_reference",
    "load_passages_for_osis",
    "validate_model_completion",
]
