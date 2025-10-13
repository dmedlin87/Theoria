"""Multi-perspective synthesis for theological reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import TYPE_CHECKING, Sequence

from theo.application.facades.settings import get_settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from ...models.search import HybridSearchFilters, HybridSearchRequest, HybridSearchResult
    from ...services.retrieval_service import RetrievalService

from ...models.search import HybridSearchFilters, HybridSearchRequest
from ...services.retrieval_service import RetrievalService
from ...retriever.hybrid import hybrid_search


@dataclass(slots=True)
class PerspectiveView:
    """A single perspective's view on a question."""

    perspective: str  # "skeptical" | "apologetic" | "neutral"
    answer: str
    confidence: float
    key_claims: list[str] = field(default_factory=list)
    citations: list["PerspectiveCitation"] = field(default_factory=list)


@dataclass(slots=True)
class PerspectiveCitation:
    """Citable evidence supporting a perspective claim."""

    document_id: str | None = None
    document_title: str | None = None
    osis: str | None = None
    snippet: str = ""
    rank: int | None = None
    score: float | None = None


@dataclass(slots=True)
class PerspectiveSynthesis:
    """Synthesis across multiple theological perspectives."""

    consensus_points: list[str]  # Claims all perspectives agree on
    tension_map: dict[str, list[str]]  # perspective -> unique claims
    meta_analysis: str  # Summary of how perspectives relate
    perspective_views: dict[str, PerspectiveView] = field(default_factory=dict)


_PERSPECTIVE_PROFILES: dict[str, dict[str, str]] = {
    "skeptical": {"theological_tradition": "skeptical"},
    "apologetic": {"theological_tradition": "apologetic"},
    "neutral": {"theological_tradition": "neutral"},
}

_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


def _resolve_retrieval_service(
    retrieval_service: "RetrievalService | None",
) -> RetrievalService:
    if retrieval_service is not None:
        return retrieval_service

    settings = get_settings()
    return RetrievalService(settings=settings, search_fn=hybrid_search)


def _prepare_filters(
    base_filters: "HybridSearchFilters | None", perspective: str
) -> HybridSearchFilters:
    profile = _PERSPECTIVE_PROFILES.get(perspective, {})
    if base_filters is None:
        filters = HybridSearchFilters()
    else:
        filters = base_filters.model_copy(deep=True)

    tradition_override = profile.get("theological_tradition")
    if tradition_override:
        filters.theological_tradition = tradition_override
    topic_override = profile.get("topic_domain")
    if topic_override:
        filters.topic_domain = topic_override
    return filters


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = _SENTENCE_PATTERN.split(text.strip())
    sentences = [segment.strip() for segment in parts if segment.strip()]
    return sentences or ([text.strip()] if text.strip() else [])


def _estimate_confidence(results: Sequence["HybridSearchResult"]) -> float:
    scores = [
        float(result.score)
        for result in results
        if getattr(result, "score", None) is not None
    ]
    if not scores:
        # fall back to a heuristic based on hit count
        return 0.15 * min(len(results), 5)

    average = sum(scores) / len(scores)
    if math.isnan(average):
        return 0.0
    # Clamp into [0, 1]
    return max(0.0, min(1.0, average))


def _extract_claims(results: list["HybridSearchResult"], *, limit: int = 3) -> list[str]:
    claims: list[str] = []
    for result in results:
        for sentence in _split_sentences(result.snippet or result.text):
            normalised = sentence.strip()
            if not normalised or normalised in claims:
                continue
            claims.append(normalised)
            if len(claims) >= limit:
                return claims
    return claims


def _build_citations(
    results: list["HybridSearchResult"], *, limit: int = 5
) -> list[PerspectiveCitation]:
    citations: list[PerspectiveCitation] = []
    for index, result in enumerate(results, start=1):
        rank = result.rank or index
        citations.append(
            PerspectiveCitation(
                document_id=result.document_id,
                document_title=getattr(result, "document_title", None),
                osis=result.osis_ref,
                snippet=result.snippet,
                rank=rank,
                score=result.score,
            )
        )
        if len(citations) >= limit:
            break
    return citations


def _compose_answer(perspective: str, claims: list[str]) -> str:
    if not claims:
        return (
            f"No {perspective} specific sources surfaced for this question."
        )
    if len(claims) == 1:
        return claims[0]
    return " ".join(claims[:2])


def _compose_meta_analysis(
    consensus_points: list[str],
    tension_map: dict[str, list[str]],
    views: dict[str, PerspectiveView],
) -> str:
    segments: list[str] = []
    if consensus_points:
        segments.append(
            "Shared ground: " + "; ".join(consensus_points) + "."
        )
    else:
        segments.append(
            "Shared ground: No overlapping claims surfaced across every perspective."
        )

    if tension_map:
        for name, claims in tension_map.items():
            summary = "; ".join(claims[:2])
            segments.append(f"{name.capitalize()} focus: {summary}.")
    else:
        segments.append("Perspective focus: No major disagreements detected.")

    missing = [name for name in _PERSPECTIVE_PROFILES if name not in views]
    if missing:
        segments.append(
            "Coverage gaps: "
            + ", ".join(name.capitalize() for name in missing)
            + " perspective not represented."
        )

    return " ".join(segments)


def synthesize_perspectives(
    question: str,
    session: Session,
    *,
    retrieval_service: RetrievalService | None = None,
    base_filters: HybridSearchFilters | None = None,
    top_k: int = 5,
) -> PerspectiveSynthesis:
    """Generate multi-perspective synthesis for a theological question.

    Runs the same question through skeptical, apologetic, and neutral lenses,
    then compares to find consensus and tensions.

    The workflow normalises perspective-specific filters, runs guarded
    retrieval, extracts headline claims, and then compares the results to map
    consensus and disagreement across stances.

    Args:
        question: The theological question
        session: Database session

    Returns:
        Multi-perspective synthesis
    """
    retrieval = _resolve_retrieval_service(retrieval_service)
    perspective_views: dict[str, PerspectiveView] = {}

    for perspective in _PERSPECTIVE_PROFILES.keys():
        filters = _prepare_filters(base_filters, perspective)
        request = HybridSearchRequest(
            query=question,
            filters=filters,
            k=max(1, min(top_k, 20)),
        )
        results, _ = retrieval.search(session, request)
        # Ensure ranks are populated for deterministic ordering
        for index, result in enumerate(results, start=1):
            result.rank = result.rank or index

        key_claims = _extract_claims(results)
        citations = _build_citations(results)
        confidence = _estimate_confidence(results)
        answer = _compose_answer(perspective, key_claims)
        perspective_views[perspective] = PerspectiveView(
            perspective=perspective,
            answer=answer,
            confidence=confidence,
            key_claims=key_claims,
            citations=citations,
        )

    populated_views = [
        view for view in perspective_views.values() if view.key_claims
    ]
    consensus_points = _find_common_ground(populated_views)
    tension_map = _map_disagreements(populated_views)
    meta_analysis = _compose_meta_analysis(
        consensus_points, tension_map, perspective_views
    )

    return PerspectiveSynthesis(
        consensus_points=consensus_points,
        tension_map=tension_map,
        meta_analysis=meta_analysis,
        perspective_views=perspective_views,
    )


def _find_common_ground(views: list[PerspectiveView]) -> list[str]:
    """Find claims that appear across all perspectives.

    Args:
        views: List of perspective views

    Returns:
        Consensus claims
    """
    if not views:
        return []

    # Extract claim sets
    claim_sets = [set(view.key_claims) for view in views]

    # Find intersection
    consensus = set.intersection(*claim_sets) if claim_sets else set()

    return list(consensus)


def _map_disagreements(views: list[PerspectiveView]) -> dict[str, list[str]]:
    """Map unique claims per perspective.

    Args:
        views: List of perspective views

    Returns:
        Dict mapping perspective name to unique claims
    """
    tension_map: dict[str, list[str]] = {}

    for view in views:
        # Find claims unique to this perspective
        other_claims = set()
        for other_view in views:
            if other_view.perspective != view.perspective:
                other_claims.update(other_view.key_claims)

        unique_claims = [
            claim for claim in view.key_claims if claim not in other_claims
        ]

        if unique_claims:
            tension_map[view.perspective] = unique_claims

    return tension_map
