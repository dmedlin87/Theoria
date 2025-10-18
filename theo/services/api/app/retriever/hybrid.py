"""Hybrid search combining pgvector ANN with lexical retrieval."""

from __future__ import annotations

import heapq
from time import perf_counter
from dataclasses import dataclass
from typing import Iterable, Sequence

from opentelemetry import trace
from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.orm import Session

from theo.application.facades.settings import get_settings
from theo.adapters.persistence.models import Document, Passage
from theo.adapters.persistence.types import VectorType
from ..ingest.embeddings import get_embedding_service
from ..ingest.osis import expand_osis_reference, osis_intersects
from ..models.documents import DocumentAnnotationResponse
from ..models.search import HybridSearchFilters, HybridSearchRequest, HybridSearchResult
from .annotations import index_annotations_by_passage, load_annotations_for_documents
from .utils import compose_passage_meta


_TRACER = trace.get_tracer("theo.retriever")


def _annotate_retrieval_span(
    span, request: HybridSearchRequest, *, cache_status: str, backend: str
) -> None:
    span.set_attribute("retrieval.backend", backend)
    span.set_attribute("retrieval.cache_status", cache_status)
    span.set_attribute("retrieval.k", request.k)
    if request.limit is not None:
        span.set_attribute("retrieval.limit", request.limit)
    if request.cursor:
        span.set_attribute("retrieval.cursor", request.cursor)
    if request.mode:
        span.set_attribute("retrieval.mode", request.mode)
    if request.query:
        span.set_attribute("retrieval.query", request.query)
    if request.osis:
        span.set_attribute("retrieval.osis", request.osis)
    filters = request.filters
    if filters.collection:
        span.set_attribute("retrieval.filter.collection", filters.collection)
    if filters.author:
        span.set_attribute("retrieval.filter.author", filters.author)
    if filters.source_type:
        span.set_attribute("retrieval.filter.source_type", filters.source_type)
    if filters.theological_tradition:
        span.set_attribute(
            "retrieval.filter.theological_tradition", filters.theological_tradition
        )
    if filters.topic_domain:
        span.set_attribute("retrieval.filter.topic_domain", filters.topic_domain)


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


def _build_highlights(
    text: str, query_tokens: list[str], *, window: int = 160, max_highlights: int = 3
) -> list[str]:
    if not query_tokens:
        return []
    lowered = text.lower()
    highlights: list[str] = []
    for token in query_tokens:
        start = 0
        while True:
            index = lowered.find(token, start)
            if index == -1:
                break
            clip_start = max(0, index - window // 3)
            clip_end = min(len(text), index + len(token) + window // 3 * 2)
            snippet = text[clip_start:clip_end].strip()
            if snippet and snippet not in highlights:
                prefix = "... " if clip_start > 0 else ""
                suffix = " ..." if clip_end < len(text) else ""
                highlights.append(f"{prefix}{snippet}{suffix}")
                if len(highlights) >= max_highlights:
                    return highlights
            start = index + len(token)
    return highlights


def _build_result(
    passage: Passage,
    document: Document,
    annotations: Sequence[DocumentAnnotationResponse] | None,
    *,
    score: float,
    lexical_score: float | None,
    vector_score: float | None,
    osis_distance: float | None,
) -> HybridSearchResult:
    meta = compose_passage_meta(passage, document)
    if annotations:
        meta = {**(meta or {})}
        meta["annotations"] = [
            annotation.model_dump(mode="json") for annotation in annotations
        ]

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
        score=score,
        meta=meta,
        document_title=document.title,
        snippet=_snippet(passage.text),
        rank=0,
        highlights=None,
        lexical_score=lexical_score,
        vector_score=vector_score,
        osis_distance=osis_distance,
    )


def _apply_document_ranks(
    results: list[HybridSearchResult],
    doc_scores: dict[str, float],
    query_tokens: list[str],
) -> list[HybridSearchResult]:
    ordered = sorted(doc_scores.items(), key=lambda item: item[1], reverse=True)
    doc_ranks = {doc_id: rank for rank, (doc_id, _score) in enumerate(ordered, start=1)}
    for result in results:
        result.document_score = doc_scores.get(result.document_id)
        result.document_rank = doc_ranks.get(result.document_id)
        result.highlights = _build_highlights(result.text, query_tokens)
    return results


def _score_candidates(
    candidates: dict[str, _Candidate],
    annotations_by_passage: dict[str, list],
    request: HybridSearchRequest,
    query_tokens: list[str],
) -> list[tuple[HybridSearchResult, float]]:
    vector_weight = 0.65
    lexical_weight = 0.35
    osis_bonus = 0.2 if request.osis else 0.0
    scored: list[tuple[HybridSearchResult, float]] = []
    for candidate in candidates.values():
        passage = candidate.passage
        document = candidate.document
        tei_score = _tei_match_score(passage, query_tokens)
        score = 0.0
        if candidate.vector_score:
            score += vector_weight * candidate.vector_score
        if candidate.lexical_score:
            score += lexical_weight * candidate.lexical_score
        annotation_notes = annotations_by_passage.get(passage.id, [])
        if request.query and annotation_notes:
            note_text = " \n".join(note.body for note in annotation_notes if note.body)
            if note_text:
                score += lexical_weight * _lexical_score(note_text, query_tokens)
        if (
            request.query
            and candidate.lexical_score == 0.0
            and candidate.vector_score == 0.0
            and tei_score == 0.0
            and not candidate.osis_match
        ):
            continue
        if (
            request.query is None
            and candidate.lexical_score == 0.0
            and candidate.vector_score == 0.0
            and tei_score == 0.0
        ):
            score = max(score, 0.1)
        if tei_score:
            score += 0.35 * tei_score
        if candidate.osis_match:
            score += osis_bonus
        result = _build_result(
            passage,
            document,
            annotation_notes,
            score=score,
            lexical_score=candidate.lexical_score or None,
            vector_score=candidate.vector_score or None,
            osis_distance=candidate.osis_distance,
        )
        scored.append((result, score))
    return scored


def _merge_scored_candidates(
    scored: list[tuple[HybridSearchResult, float]],
    request: HybridSearchRequest,
    query_tokens: list[str],
) -> list[HybridSearchResult]:
    scored.sort(key=lambda item: item[1], reverse=True)
    limited = scored[: request.k]
    results: list[HybridSearchResult] = []
    for idx, (result, score) in enumerate(limited, start=1):
        result.rank = idx
        result.score = score
        results.append(result)

    doc_scores: dict[str, float] = {}
    for result in results:
        doc_scores[result.document_id] = max(
            doc_scores.get(result.document_id, float("-inf")), result.score or 0.0
        )

    return _apply_document_ranks(results, doc_scores, query_tokens)


@dataclass
class _Candidate:
    passage: Passage
    document: Document
    vector_score: float = 0.0
    lexical_score: float = 0.0
    osis_match: bool = False
    osis_distance: float | None = None


def _osis_distance_value(candidate_ref: str | None, target_ref: str | None) -> float | None:
    if not candidate_ref or not target_ref:
        return None
    candidate_ids = expand_osis_reference(candidate_ref)
    target_ids = expand_osis_reference(target_ref)
    if not candidate_ids or not target_ids:
        return None
    if not candidate_ids.isdisjoint(target_ids):
        return 0.0
    return float(min(abs(a - b) for a in candidate_ids for b in target_ids))


def _mark_candidate_osis(candidate: _Candidate, target_ref: str) -> None:
    candidate.osis_match = True
    distance = _osis_distance_value(candidate.passage.osis_ref, target_ref)
    if distance is None:
        return
    if candidate.osis_distance is None or distance < candidate.osis_distance:
        candidate.osis_distance = distance


def _passes_author_filter(document: Document, author: str | None) -> bool:
    if not author:
        return True
    if not document.authors:
        return False
    return author in document.authors


def _normalise_filter_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized.casefold()


def _matches_tradition(document: Document, filter_value: str | None) -> bool:
    target = _normalise_filter_value(filter_value)
    if target is None:
        return True
    candidate = _normalise_filter_value(document.theological_tradition)
    return candidate == target


def _matches_topic_domain(document: Document, filter_value: str | None) -> bool:
    target = _normalise_filter_value(filter_value)
    if target is None:
        return True
    domains = document.topic_domains or []
    for domain in domains:
        if _normalise_filter_value(domain) == target:
            return True
    return False


def _passes_guardrail_filters(
    document: Document, filters: HybridSearchFilters
) -> bool:
    if not _matches_tradition(document, filters.theological_tradition):
        return False
    if not _matches_topic_domain(document, filters.topic_domain):
        return False
    return True


def _tei_terms(passage: Passage) -> list[str]:
    meta = passage.meta or {}
    if not isinstance(meta, dict):
        return []
    terms: list[str] = []
    tei_section = meta.get("tei")
    if isinstance(tei_section, dict):
        for values in tei_section.values():
            if isinstance(values, list):
                terms.extend(str(value) for value in values)
            elif isinstance(values, dict):
                terms.extend(str(value) for value in values.values())
    search_blob = meta.get("tei_search_blob")
    if isinstance(search_blob, str):
        terms.extend(search_blob.split())
    return [term for term in terms if term]


def _tei_match_score(passage: Passage, query_tokens: Iterable[str]) -> float:
    lowered_terms = " ".join(term.lower() for term in _tei_terms(passage))
    if not lowered_terms:
        return 0.0
    score = 0.0
    for token in query_tokens:
        score += lowered_terms.count(token)
    return score


def _apply_common_filters(stmt, request: HybridSearchRequest):
    if request.filters.collection:
        stmt = stmt.where(Document.collection == request.filters.collection)
    if request.filters.source_type:
        stmt = stmt.where(Document.source_type == request.filters.source_type)
    return stmt


def _build_base_query(request: HybridSearchRequest):
    stmt = select(Passage, Document).join(Document)
    return _apply_common_filters(stmt, request)


def _build_vector_statement(
    base_stmt, query_embedding: list[float], limit: int, *, embedding_dim: int
):
    vector_param = literal(query_embedding, type_=VectorType(embedding_dim))
    distance = func.cosine_distance(Passage.embedding, vector_param).label("distance")
    vector_score_expr = (1.0 - func.coalesce(distance, 1.0)).label("vector_score")
    return (
        base_stmt.add_columns(distance, vector_score_expr)
        .where(Passage.embedding.isnot(None))
        .order_by(distance.asc())
        .limit(limit)
    )


def _build_lexical_statement(base_stmt, request: HybridSearchRequest, limit: int):
    ts_query = func.plainto_tsquery("english", request.query)
    lexical_rank = func.ts_rank_cd(Passage.lexeme, ts_query).label("lexical_score")
    return (
        base_stmt.add_columns(lexical_rank)
        .where(Passage.lexeme.isnot(None))
        .where(Passage.lexeme.op("@@")(ts_query))
        .order_by(lexical_rank.desc())
        .limit(limit)
    )


def _build_tei_statement(base_stmt, query_tokens: list[str], limit: int):
    tei_blob = Passage.meta["tei_search_blob"].astext
    tei_facet_blob = Passage.meta["tei"].astext
    tei_like_clauses = []
    for token in query_tokens:
        like_value = f"%{token}%"
        tei_like_clauses.append(tei_blob.ilike(like_value))
        tei_like_clauses.append(tei_facet_blob.ilike(like_value))
    tei_present = or_(tei_blob.isnot(None), tei_facet_blob.isnot(None))
    if tei_like_clauses:
        return base_stmt.where(tei_present).where(or_(*tei_like_clauses)).limit(limit)
    return base_stmt.where(tei_present).limit(limit)


def _fallback_search(
    session: Session, request: HybridSearchRequest
) -> list[HybridSearchResult]:
    start = perf_counter()
    cache_status = "miss"
    with _TRACER.start_as_current_span("retriever.fallback") as span:
        _annotate_retrieval_span(
            span, request, cache_status=cache_status, backend="fallback"
        )

        query_tokens = _tokenise(request.query or "")

        stmt = _build_base_query(request)
        if request.query and not request.osis:
            token_clauses = []
            tei_blob = func.json_extract(Passage.meta, "$.tei_search_blob")
            for token in query_tokens:
                like_value = f"%{token}%"
                token_clauses.append(
                    or_(
                        Passage.text.ilike(like_value),
                        tei_blob.isnot(None) & tei_blob.ilike(like_value),
                    )
                )
            if token_clauses:
                stmt = stmt.where(and_(*token_clauses))
        if request.osis:
            stmt = stmt.where(Passage.osis_ref.isnot(None))

        limit = max(request.k * 10, 100)
        stmt = stmt.limit(limit)

        rows = session.execute(stmt).all()
        doc_ids = [document.id for _passage, document in rows]
        annotations_by_document = load_annotations_for_documents(session, doc_ids)
        annotations_by_passage = index_annotations_by_passage(
            annotations_by_document
        )

        heap: list[tuple[float, int, HybridSearchResult]] = []
        counter = 0
        for passage, document in rows:
            if not _passes_author_filter(document, request.filters.author):
                continue
            if not _passes_guardrail_filters(document, request.filters):
                continue

            annotation_notes = annotations_by_passage.get(passage.id, [])
            note_texts = [note.body for note in annotation_notes if note.body]
            combined_text = (
                " \n".join([passage.text, *note_texts]) if note_texts else passage.text
            )
            lexical = _lexical_score(combined_text, query_tokens)
            tei_score = _tei_match_score(passage, query_tokens)
            osis_distance = _osis_distance_value(passage.osis_ref, request.osis)
            osis_match = bool(osis_distance == 0.0)
            if request.osis and not osis_match and lexical == 0.0:
                continue

            if request.query and lexical == 0.0 and tei_score == 0.0 and not osis_match:
                continue

            score = lexical + 0.5 * tei_score
            if osis_match:
                score += 5.0
            if request.query and passage.lexeme:
                score += 0.1 * len(request.query)

            result = _build_result(
                passage,
                document,
                annotation_notes,
                score=score,
                lexical_score=lexical,
                vector_score=None,
                osis_distance=osis_distance,
            )

            heapq.heappush(heap, (score, counter, result))
            if len(heap) > limit:
                heapq.heappop(heap)
            counter += 1

        sorted_results = sorted(heap, key=lambda item: item[0], reverse=True)[
            : request.k
        ]
        final: list[HybridSearchResult] = []
        doc_scores: dict[str, float] = {}
        for score, _counter, result in sorted_results:
            doc_scores[result.document_id] = max(
                doc_scores.get(result.document_id, float("-inf")), score
            )
        for idx, (score, _counter, result) in enumerate(sorted_results, start=1):
            result.rank = idx
            result.score = score
            final.append(result)

        results = _apply_document_ranks(final, doc_scores, query_tokens)
        latency_ms = (perf_counter() - start) * 1000.0
        span.set_attribute("retrieval.hit_count", len(results))
        span.set_attribute("retrieval.latency_ms", round(latency_ms, 2))
        return results


def _postgres_hybrid_search(
    session: Session, request: HybridSearchRequest
) -> list[HybridSearchResult]:
    settings = get_settings()
    embedding_service = get_embedding_service()
    dialect = session.bind.dialect if session.bind is not None else None
    if dialect is None or dialect.name != "postgresql":
        return _fallback_search(session, request)

    start = perf_counter()
    cache_status = "miss"
    with _TRACER.start_as_current_span("retriever.postgres") as span:
        _annotate_retrieval_span(
            span, request, cache_status=cache_status, backend="postgresql"
        )

        candidates: dict[str, _Candidate] = {}
        limit = max(request.k * 4, 20)
        query_tokens = _tokenise(request.query or "")

        base_stmt = _build_base_query(request)

        query_embedding: list[float] | None = None
        if request.query:
            query_embedding = embedding_service.embed([request.query])[0]
            vector_stmt = _build_vector_statement(
                base_stmt, query_embedding, limit, embedding_dim=settings.embedding_dim
            )
            for row in session.execute(vector_stmt):
                passage: Passage = row[0]
                document: Document = row[1]
                if not _passes_author_filter(document, request.filters.author):
                    continue
                if not _passes_guardrail_filters(document, request.filters):
                    continue
                if request.osis and not (
                    passage.osis_ref and osis_intersects(passage.osis_ref, request.osis)
                ):
                    continue
                key = passage.id
                candidate = candidates.get(key)
                if not candidate:
                    candidate = _Candidate(passage=passage, document=document)
                    candidates[key] = candidate
                candidate.vector_score = max(
                    candidate.vector_score, float(row[3] or 0.0)
                )
                if request.osis:
                    _mark_candidate_osis(candidate, request.osis)

        if request.query:
            lexical_stmt = _build_lexical_statement(base_stmt, request, limit)
            for row in session.execute(lexical_stmt):
                passage: Passage = row[0]
                document: Document = row[1]
                if not _passes_author_filter(document, request.filters.author):
                    continue
                if not _passes_guardrail_filters(document, request.filters):
                    continue
                if request.osis and not (
                    passage.osis_ref and osis_intersects(passage.osis_ref, request.osis)
                ):
                    continue
                key = passage.id
                candidate = candidates.get(key)
                if not candidate:
                    candidate = _Candidate(passage=passage, document=document)
                    candidates[key] = candidate
                candidate.lexical_score = max(
                    candidate.lexical_score, float(row[2] or 0.0)
                )
                if request.osis:
                    _mark_candidate_osis(candidate, request.osis)

            tei_stmt = _build_tei_statement(base_stmt, query_tokens, limit)
            for passage, document in session.execute(tei_stmt):
                if not _passes_author_filter(document, request.filters.author):
                    continue
                if not _passes_guardrail_filters(document, request.filters):
                    continue
                if request.osis and not (
                    passage.osis_ref and osis_intersects(passage.osis_ref, request.osis)
                ):
                    continue
                key = passage.id
                candidate = candidates.get(key)
                if not candidate:
                    candidate = _Candidate(passage=passage, document=document)
                    candidates[key] = candidate
                if request.osis:
                    _mark_candidate_osis(candidate, request.osis)

        if request.osis and (not request.query or not candidates):
            osis_stmt = base_stmt.where(Passage.osis_ref.isnot(None)).limit(limit)
            for passage, document in session.execute(osis_stmt):
                if not _passes_author_filter(document, request.filters.author):
                    continue
                if not _passes_guardrail_filters(document, request.filters):
                    continue
                if not (
                    passage.osis_ref and osis_intersects(passage.osis_ref, request.osis)
                ):
                    continue
                key = passage.id
                candidate = candidates.get(key)
                if not candidate:
                    candidate = _Candidate(passage=passage, document=document)
                    candidates[key] = candidate
                _mark_candidate_osis(candidate, request.osis)

        if not candidates and not request.query:
            latency_ms = (perf_counter() - start) * 1000.0
            span.set_attribute("retrieval.hit_count", 0)
            span.set_attribute("retrieval.latency_ms", round(latency_ms, 2))
            return []

        doc_ids = [candidate.document.id for candidate in candidates.values()]
        annotations_by_document = load_annotations_for_documents(session, doc_ids)
        annotations_by_passage = index_annotations_by_passage(
            annotations_by_document
        )

        scored = _score_candidates(candidates, annotations_by_passage, request, query_tokens)
        results = _merge_scored_candidates(scored, request, query_tokens)
        latency_ms = (perf_counter() - start) * 1000.0
        span.set_attribute("retrieval.hit_count", len(results))
        span.set_attribute("retrieval.latency_ms", round(latency_ms, 2))
        return results


def hybrid_search(
    session: Session, request: HybridSearchRequest
) -> list[HybridSearchResult]:
    """Perform hybrid search using pgvector when available."""

    start = perf_counter()
    cache_status = "miss"
    with _TRACER.start_as_current_span("retriever.hybrid") as span:
        _annotate_retrieval_span(
            span, request, cache_status=cache_status, backend="hybrid"
        )
        bind = getattr(session, "bind", None)
        if bind is None or bind.dialect.name != "postgresql":
            span.set_attribute("retrieval.selected_backend", "fallback")
            results = _fallback_search(session, request)
        else:
            span.set_attribute("retrieval.selected_backend", "postgresql")
            results = _postgres_hybrid_search(session, request)
        latency_ms = (perf_counter() - start) * 1000.0
        span.set_attribute("retrieval.hit_count", len(results))
        span.set_attribute("retrieval.latency_ms", round(latency_ms, 2))
        return results
