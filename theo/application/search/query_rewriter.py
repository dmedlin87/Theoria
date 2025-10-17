"""Query rewriting utilities for hybrid search."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping, Sequence

from pydantic import BaseModel

from theo.domain.research.osis import osis_to_readable

try:  # pragma: no cover - pythonbible optional during static analysis
    from pythonbible import InvalidVerseError
except Exception:  # pragma: no cover - type checkers still need the name
    class InvalidVerseError(Exception):
        """Fallback exception used when pythonbible is unavailable."""


_GUARDRAIL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:ignore|disregard|forget)\b[^\n]{0,40}?\b(?:previous|prior|all)\s+instructions?\b",
            re.IGNORECASE,
        ),
        "[filtered-instruction]",
    ),
    (
        re.compile(
            r"\b(?:override|disable|bypass|reset)\b[^\n]{0,40}?\b(?:guardrails?|safety|system)\b",
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
)

_DEFAULT_SYNONYMS: Mapping[str, Sequence[str]] = {
    "atonement": ("propitiation", "reconciliation"),
    "love": ("agape", "charity"),
    "faith": ("belief", "trust"),
}


@dataclass(slots=True)
class QueryRewriteResult:
    """Structured response describing a rewrite operation."""

    request: BaseModel
    metadata: dict[str, object]


class QueryRewriter:
    """Augment user queries with semantic and guardrail-aware hints."""

    def __init__(
        self,
        *,
        synonym_index: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self._synonym_index: Mapping[str, Sequence[str]] = {
            key.lower(): tuple(values)
            for key, values in (synonym_index or _DEFAULT_SYNONYMS).items()
        }

    def rewrite(self, request: BaseModel) -> QueryRewriteResult:
        """Return a modified request with expanded query context."""

        # Work on a deep copy to avoid mutating the caller's object.
        cloned = request.model_copy(deep=True)

        original_query = getattr(request, "query", None)
        osis_hint = getattr(request, "osis", None)

        sanitized_query = self._scrub_guardrail_patterns(original_query)
        base_query = sanitized_query if sanitized_query is not None else original_query

        synonyms = self._collect_synonyms(base_query)
        osis_hints = self._build_osis_hints(osis_hint)

        expanded_terms: list[str] = []
        if base_query:
            expanded_terms.append(base_query)
        expanded_terms.extend(synonyms)
        expanded_terms.extend(osis_hints)

        expanded_query = self._join_unique_terms(expanded_terms)

        metadata = self._build_metadata(
            original_query=original_query,
            sanitized_query=sanitized_query,
            synonyms=synonyms,
            osis_hints=osis_hints,
            expanded_query=expanded_query,
        )

        if expanded_query is not None:
            setattr(cloned, "query", expanded_query)

        return QueryRewriteResult(request=cloned, metadata=metadata)

    def _collect_synonyms(self, query: str | None) -> list[str]:
        if not query:
            return []
        lowered = query.lower()
        expansions: list[str] = []
        for token, synonyms in self._synonym_index.items():
            # Use word-boundary regex to match token as a whole word
            pattern = re.compile(r"\b{}\b".format(re.escape(token)), re.IGNORECASE)
            if pattern.search(query):
                for synonym in synonyms:
                    if synonym and not re.search(r"\b{}\b".format(re.escape(synonym)), lowered):
                        expansions.append(synonym)
        return expansions

    def _build_osis_hints(self, osis_value: str | None) -> list[str]:
        if not osis_value:
            return []
        try:
            readable = osis_to_readable(osis_value)
        except InvalidVerseError:
            return []
        except Exception:
            return []
        return [readable]

    def _scrub_guardrail_patterns(self, query: str | None) -> str | None:
        if query is None:
            return None
        text = query
        for pattern, replacement in _GUARDRAIL_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def _join_unique_terms(self, terms: Iterable[str]) -> str | None:
        seen: set[str] = set()
        ordered: list[str] = []
        for term in terms:
            cleaned = term.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(cleaned)
        if not ordered:
            return None
        return " ".join(ordered)

    def _build_metadata(
        self,
        *,
        original_query: str | None,
        sanitized_query: str | None,
        synonyms: Sequence[str],
        osis_hints: Sequence[str],
        expanded_query: str | None,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {
            "original_query": original_query,
        }
        if sanitized_query is not None and sanitized_query != original_query:
            metadata["guardrail_sanitized"] = sanitized_query
        if synonyms:
            metadata["synonym_expansions"] = list(synonyms)
        if osis_hints:
            metadata["osis_hints"] = list(osis_hints)
        if expanded_query is not None and expanded_query != original_query:
            metadata["expanded_query"] = expanded_query
            metadata["rewrite_applied"] = True
        else:
            metadata["rewrite_applied"] = False
        return metadata


__all__ = ["QueryRewriteResult", "QueryRewriter"]
