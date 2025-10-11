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

from ...db.models import Document, Passage
from ...models.search import HybridSearchFilters, HybridSearchResult
from ..clients import GenerationError
from .models import RAGAnswer, RAGCitation
from .prompts import sanitise_json_structure

LOGGER = logging.getLogger(__name__)

_CITATION_ENTRY_PATTERN = re.compile(
    r"^\[(?P<index>\d+)]\s*(?P<osis>[^()]+?)\s*\((?P<anchor>[^()]+)\)$"
)
_SENTENCE_PATTERN = re.compile(r"[^.!?]*[.!?]|[^.!?]+$")

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
    (re.compile(r"<\s*/?script\b", re.IGNORECASE), "script markup"),
    (re.compile(r"password\s*[:=]", re.IGNORECASE), "credential disclosure"),
    (re.compile(r"api[-_\s]*key", re.IGNORECASE), "credential disclosure"),
    (re.compile(r"access\s*token", re.IGNORECASE), "credential disclosure"),
    (re.compile(r"secret\s*(?:key|token)", re.IGNORECASE), "credential disclosure"),
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
        raise GuardrailError(
            "No passages matched the requested guardrail profile",
            safe_refusal=True,
            metadata={
                "code": "guardrail_profile_no_match",
                "guardrail": "retrieval",
                "suggested_action": "search",
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


def validate_model_completion(
    completion: str,
    citations: Sequence[RAGCitation],
) -> dict[str, Any]:
    if not completion or not completion.strip():
        raise GuardrailError(
            "Model completion was empty",
            metadata={
                "code": "generation_empty_completion",
                "guardrail": "generation",
                "suggested_action": "search",
            },
        )

    marker_index = completion.lower().rfind("sources:")
    if marker_index == -1:
        raise GuardrailError(
            "Model completion missing 'Sources:' line",
            metadata={
                "code": "generation_missing_sources_line",
                "guardrail": "generation",
                "suggested_action": "search",
            },
        )

    sources_text = completion[marker_index + len("Sources:") :].strip()
    if not sources_text:
        raise GuardrailError(
            "Model completion missing citations after 'Sources:'",
            metadata={
                "code": "generation_missing_citations",
                "guardrail": "generation",
                "suggested_action": "search",
            },
        )

    entries = [entry.strip() for entry in re.split(r";|\n", sources_text) if entry.strip()]
    if not entries:
        raise GuardrailError(
            "Model completion missing citations after 'Sources:'",
            metadata={
                "code": "generation_missing_citations",
                "guardrail": "generation",
                "suggested_action": "search",
            },
        )

    expected = {citation.index: citation for citation in citations}
    mismatches: list[str] = []
    parsed_entries: list[dict[str, Any]] = []
    cited_indices: list[int] = []

    for entry in entries:
        entry_match = _CITATION_ENTRY_PATTERN.match(entry)
        if not entry_match:
            mismatches.append(f"unparsable citation '{entry}'")
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
        raise GuardrailError(
            "Model completion did not include any recognised citations",
            metadata={
                "code": "generation_unrecognised_citations",
                "guardrail": "generation",
                "suggested_action": "search",
            },
        )

    if mismatches:
        raise GuardrailError(
            "Model citations failed guardrails: " + "; ".join(mismatches),
            metadata={
                "code": "generation_citation_mismatch",
                "guardrail": "generation",
                "suggested_action": "search",
                "reason": "; ".join(mismatches),
            },
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
