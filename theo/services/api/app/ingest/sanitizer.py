"""Utilities for removing prompt-injection control phrases from passages."""

from __future__ import annotations

import re
from typing import Final

__all__ = ["sanitize_passage_text"]

# Regex patterns that identify instruction-style control phrases that should not
# be stored verbatim in the embeddings database or fed back to the language
# model. The expressions aim to catch common prompt-injection templates without
# being overly aggressive so that legitimate prose is preserved.
_DANGEROUS_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(?is)<script[^>]*>.*?</script>"),
    re.compile(r"(?is)<style[^>]*>.*?</style>"),
    re.compile(r"(?is)<meta[^>]+http-equiv[^>]*>"),
    re.compile(r"(?is)<!--.*?prompt-injection.*?-->"),
    re.compile(r"(?i)\bignore\s+(?:all\s+)?previous\s+instructions\b"),
    re.compile(r"(?i)\bdisregard\s+the\s+(?:above|prior)\s+instructions?\b"),
    re.compile(r"(?i)\b(?:system|assistant|user)\s*:\s*"),
    re.compile(r"(?i)\breset\s+the\s+system\s+prompt\b"),
    re.compile(r"(?i)\boverride\s+the\s+guardrails\b"),
)

# Secondary normalisation patterns to tidy up whitespace introduced when the
# control phrases are removed.
_WHITESPACE_NORMALISERS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"\s{2,}"), " "),
    (re.compile(r"\n{3,}"), "\n\n"),
)

def sanitize_passage_text(text: str) -> str:
    """Return *text* with prompt-injection control phrases removed."""

    if not text:
        return ""

    sanitized = text
    for pattern in _DANGEROUS_PATTERNS:
        sanitized = pattern.sub(" ", sanitized)

    for pattern, replacement in _WHITESPACE_NORMALISERS:
        sanitized = pattern.sub(replacement, sanitized)

    sanitized = sanitized.strip()
    if sanitized:
        return sanitized
    if text and text.strip():
        return "[filtered]"
    return ""
