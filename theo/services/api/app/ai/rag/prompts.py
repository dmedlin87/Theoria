"""Prompt construction utilities for guardrailed RAG workflows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from ...models.search import HybridSearchFilters, HybridSearchResult

from .models import RAGCitation


_MARKDOWN_ESCAPE_PATTERN = re.compile(r"([\\`*_{}\[\]()#+.!|\-])")
_ADVERSARIAL_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
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
    (re.compile(r"drop\s+table\b", re.IGNORECASE), "[filtered-sql]"),
    (
        re.compile(r"<\s*/?script\b[^>]*>", re.IGNORECASE),
        "[filtered-html]",
    ),
    (
        re.compile(r"<\s*/?style\b[^>]*>", re.IGNORECASE),
        "[filtered-html]",
    ),
    (re.compile(r"<!--.*?-->", re.DOTALL), "[filtered-comment]"),
    (
        re.compile(r"```(?:html|javascript|sql)[\s\S]*?```", re.IGNORECASE),
        "[filtered-code-block]",
    ),
)


_MOJIBAKE_TRIGGERS = ("Ã", "â")
_MOJIBAKE_SEQUENCE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("â€”", "—"),
    ("â€“", "–"),
    ("â€˜", "‘"),
    ("â€™", "’"),
    ("â€œ", "“"),
    ("â€�", "”"),
    ("â€¦", "…"),
    ("Ã©", "é"),
    ("Ã¨", "è"),
    ("Ãª", "ê"),
    ("Ã«", "ë"),
    ("Ã¡", "á"),
    ("Ã ", "à"),
    ("Ã¤", "ä"),
    ("Ã†", "Æ"),
    ("Ã¶", "ö"),
    ("Ã¼", "ü"),
)


def _normalise_mojibake(text: str) -> str:
    """Best-effort fix for mojibake sequences seen in legacy corpora."""

    if not text or not any(trigger in text for trigger in _MOJIBAKE_TRIGGERS):
        return text
    normalised: str | None = None
    for encoding in ("latin-1", "cp1252"): 
        try:
            normalised = text.encode(encoding).decode("utf-8")
            break
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    candidate = normalised or text
    if any(trigger in candidate for trigger in _MOJIBAKE_TRIGGERS):
        for mojibake, replacement in _MOJIBAKE_SEQUENCE_REPLACEMENTS:
            candidate = candidate.replace(mojibake, replacement)
    return candidate


def scrub_adversarial_language(value: str | None) -> str | None:
    if not value:
        return value
    text = _normalise_mojibake(value)
    for pattern, replacement in _ADVERSARIAL_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def escape_markdown_html(value: str) -> str:
    if not value:
        return ""
    escaped = (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return _MARKDOWN_ESCAPE_PATTERN.sub(r"\\\1", escaped)


def sanitise_markdown_field(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    text = _normalise_mojibake(text)
    return escape_markdown_html(text)


def sanitise_json_structure(payload: object) -> object:
    if isinstance(payload, dict):
        return {key: sanitise_json_structure(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple, set)):
        return [sanitise_json_structure(item) for item in payload]
    if isinstance(payload, str):
        return sanitise_markdown_field(payload)
    return payload


@dataclass(slots=True)
class PromptContext:
    citations: Sequence[RAGCitation]
    filters: HybridSearchFilters | None = None
    memory_context: Sequence[str] | None = None

    def _normalise_part(self, value: str) -> str:
        """Normalise prompt segments to smooth out legacy encoding artefacts."""

        return _normalise_mojibake(value) if value else value

    def _format_context_lines(self) -> list[str]:
        lines: list[str] = []
        for citation in self.citations:
            prompt_snippet = scrub_adversarial_language(citation.snippet) or ""
            line = (
                f"[{citation.index}] {prompt_snippet.strip()} (OSIS {citation.osis}, {citation.anchor})"
            )
            lines.append(self._normalise_part(line))
        return lines

    def build_prompt(self, question: str | None) -> str:
        parts = [
            "You are Theo Engine's grounded assistant.",
            "Answer the question strictly from the provided passages.",
            "Cite evidence using the bracketed indices and retain OSIS + anchor in a Sources line.",
            "If the passages do not answer the question, state that explicitly.",
        ]
        if self.memory_context:
            parts.append("Prior conversation highlights:")
            for idx, snippet in enumerate(self.memory_context, start=1):
                sanitized = scrub_adversarial_language(snippet) or ""
                if sanitized:
                    parts.append(self._normalise_part(f"{idx}. {sanitized}"))
        sanitized_question = scrub_adversarial_language(question)
        if sanitized_question:
            parts.append(self._normalise_part(f"Question: {sanitized_question}"))
        parts.append("Passages:")
        parts.extend(self._format_context_lines())
        parts.append("Respond with 2-3 sentences followed by 'Sources:'")
        return "\n".join(self._normalise_part(part) for part in parts)

    def build_summary(self, results: Sequence[HybridSearchResult]) -> tuple[str, list[str]]:
        cited_results = [result for result in results if result.osis_ref]
        summary_lines: list[str] = []
        for idx, citation in enumerate(self.citations):
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
        return "\n".join(summary_lines), summary_lines


__all__ = [
    "PromptContext",
    "RAGCitation",
    "escape_markdown_html",
    "sanitise_json_structure",
    "sanitise_markdown_field",
    "scrub_adversarial_language",
]
