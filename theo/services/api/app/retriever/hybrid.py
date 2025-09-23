"""Hybrid search interface (vector + lexical)."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from ..db.models import Document, Passage
from ..ingest.osis import osis_intersects
from ..models.search import HybridSearchRequest, HybridSearchResult


def _tokenise(text: str) -> list[str]:
    return [token for token in text.lower().split() if token]


def _lexical_score(text: str, query_tokens: Iterable[str]) -> float:
    if not query_tokens:
        return 0.0
    lowered = text.lower()
    score = 0.0
    for token in query_tokens:
        score += lowered.count(token)
    return score


def _snippet(text: str, max_length: int = 240) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def hybrid_search(session: Session, request: HybridSearchRequest) -> list[HybridSearchResult]:
    """Perform a lightweight hybrid search using lexical heuristics."""

    query_tokens = _tokenise(request.query or "")
    stmt = session.query(Passage, Document).join(Document)
    candidates: list[tuple[Passage, Document]] = list(stmt)

    results: list[tuple[HybridSearchResult, float]] = []
    for passage, document in candidates:
        if request.filters.collection and document.collection != request.filters.collection:
            continue
        if request.filters.source_type and document.source_type != request.filters.source_type:
            continue
        if request.filters.author and (not document.authors or request.filters.author not in document.authors):
            continue

        lexical = _lexical_score(passage.text, query_tokens)
        osis_match = False
        if request.osis:
            if passage.osis_ref and osis_intersects(passage.osis_ref, request.osis):
                osis_match = True
            elif not lexical:
                # Skip non matching passages when only an OSIS filter is provided.
                continue

        if not lexical and not osis_match and not request.query:
            continue

        score = lexical
        if osis_match:
            score += 5.0
        if request.query and passage.lexeme:
            score += 0.1 * len(request.query)

        result = HybridSearchResult(
            id=passage.id,
            document_id=passage.document_id,
            text=passage.text,
            osis_ref=passage.osis_ref,
            page_no=passage.page_no,
            t_start=passage.t_start,
            t_end=passage.t_end,
            score=score,
            meta=passage.meta,
            document_title=document.title,
            snippet=_snippet(passage.text),
            rank=0,
            highlights=None,
        )
        results.append((result, score))

    results.sort(key=lambda item: item[1], reverse=True)
    limited = results[: request.k]
    final: list[HybridSearchResult] = []
    for idx, (result, score) in enumerate(limited, start=1):
        result.rank = idx
        result.score = score
        final.append(result)
    return final
