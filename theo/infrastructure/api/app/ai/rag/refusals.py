"""Guardrail refusal helpers for guardrailed RAG workflows."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.infrastructure.api.app.persistence_models import Document, Passage

from ...models.search import HybridSearchResult
from .guardrail_helpers import derive_snippet, format_anchor
from .models import RAGAnswer, RAGCitation

LOGGER = logging.getLogger(__name__)

_REFUSAL_OSIS = "John.1.1"
_REFUSAL_FALLBACK_ANCHOR = "John 1:1"
_REFUSAL_FALLBACK_TITLE = "Guardrail Reference"
_REFUSAL_FALLBACK_SNIPPET = (
    "John 1:1 affirms the Word as divine and life-giving; our responses must remain "
    "grounded in that hope."
)

REFUSAL_MODEL_NAME = "guardrail.refusal"
REFUSAL_MESSAGE = "I'm sorry, but I cannot help with that request."


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
        snippet = derive_snippet(result, fallback=_REFUSAL_FALLBACK_SNIPPET)
        anchor = format_anchor(result)

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


def build_guardrail_refusal(session: Session, *, reason: str | None = None) -> RAGAnswer:
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


__all__ = [
    "REFUSAL_MESSAGE",
    "REFUSAL_MODEL_NAME",
    "build_guardrail_refusal",
]
