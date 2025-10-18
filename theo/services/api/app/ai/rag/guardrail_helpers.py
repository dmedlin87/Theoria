"""Helper utilities that bridge guardrail and prompt functionality for RAG workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from sqlalchemy.orm import Session

from theo.adapters.persistence.models import Document, Passage
from ...models.search import HybridSearchFilters, HybridSearchResult
from .guardrails import (
    GuardrailError,
    apply_guardrail_profile as _guardrails_apply_guardrail_profile,
    build_citations as _guardrails_build_citations,
    build_guardrail_result as _guardrails_build_guardrail_result,
    build_retrieval_digest as _guardrails_build_retrieval_digest,
    ensure_completion_safe as _guardrails_ensure_completion_safe,
    load_guardrail_reference as _guardrails_load_guardrail_reference,
    load_passages_for_osis as _guardrails_load_passages_for_osis,
    validate_model_completion as _guardrails_validate_model_completion,
)
from .guardrails import _derive_snippet as _guardrails_derive_snippet
from .guardrails import _format_anchor as _guardrails_format_anchor
from .guardrails import _normalise_snippet as _guardrails_normalise_snippet
from .prompts import sanitise_json_structure as _prompts_sanitize_json_structure
from .prompts import sanitise_markdown_field as _prompts_sanitize_markdown_field
from .prompts import scrub_adversarial_language as _prompts_scrub_adversarial_language

if TYPE_CHECKING:  # pragma: no cover - hints only
    from .models import RAGCitation


def scrub_adversarial_language(value: str | None) -> str | None:
    """Remove adversarial patterns from model inputs."""

    return _prompts_scrub_adversarial_language(value)


def sanitize_json_structure(payload: Any) -> Any:
    """Sanitise values destined for JSON serialisation."""

    return _prompts_sanitize_json_structure(payload)


def sanitize_markdown_field(value: object) -> str:
    """Ensure text inserted into Markdown front matter is safe."""

    return _prompts_sanitize_markdown_field(value)


def apply_guardrail_profile(
    results: Sequence[HybridSearchResult],
    filters: HybridSearchFilters | None,
) -> tuple[list[HybridSearchResult], dict[str, str] | None]:
    """Apply the configured guardrail profile to retrieved passages."""

    return _guardrails_apply_guardrail_profile(results, filters)


def build_citations(results: Sequence[HybridSearchResult]) -> list["RAGCitation"]:
    """Construct RAG citations for ordered retrieval results."""

    from .models import RAGCitation  # Imported lazily to avoid circular dependencies.

    return _guardrails_build_citations(results)


def build_guardrail_result(passage: Passage, document: Document | None) -> HybridSearchResult:
    """Construct a hybrid search result suitable for guardrail fallback usage."""

    return _guardrails_build_guardrail_result(passage, document)


def build_retrieval_digest(results: Sequence[HybridSearchResult]) -> str:
    """Create a stable hash summarising the retrieval inputs."""

    return _guardrails_build_retrieval_digest(results)


def validate_model_completion(
    completion: str,
    citations: Sequence["RAGCitation"],
) -> dict[str, Any]:
    """Validate that a model completion adheres to guardrail expectations."""

    from .models import RAGCitation  # Imported lazily to avoid circular dependencies.

    return _guardrails_validate_model_completion(completion, citations)


def ensure_completion_safe(completion: str | None) -> None:
    """Raise if unsafe patterns are found in a completion."""

    _guardrails_ensure_completion_safe(completion)


def load_guardrail_reference(session: Session) -> HybridSearchResult | None:
    """Return a fallback passage when retrieval fails to ground an answer."""

    return _guardrails_load_guardrail_reference(session)


def load_passages_for_osis(
    session: Session, osis: str, *, limit: int = 3
) -> list[HybridSearchResult]:
    """Load passages matching the requested OSIS reference."""

    return _guardrails_load_passages_for_osis(session, osis, limit=limit)


def format_anchor(passage: HybridSearchResult | Passage) -> str:
    """Format an anchor description for a passage."""

    return _guardrails_format_anchor(passage)


def derive_snippet(
    result: HybridSearchResult,
    *,
    text: str | None = None,
    fallback: str | None = None,
) -> str:
    """Derive a contextual snippet from a passage result."""

    return _guardrails_derive_snippet(result, text=text, fallback=fallback)


def normalise_snippet(text: str) -> str:
    """Normalise whitespace and truncate long snippets."""

    return _guardrails_normalise_snippet(text)


__all__ = [
    "GuardrailError",
    "apply_guardrail_profile",
    "build_citations",
    "build_guardrail_result",
    "build_retrieval_digest",
    "derive_snippet",
    "ensure_completion_safe",
    "format_anchor",
    "load_guardrail_reference",
    "load_passages_for_osis",
    "normalise_snippet",
    "sanitize_json_structure",
    "sanitize_markdown_field",
    "scrub_adversarial_language",
    "validate_model_completion",
]
