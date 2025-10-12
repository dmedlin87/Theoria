from __future__ import annotations

from dataclasses import dataclass

from theo.services.api.app.ai.reasoning.perspectives import synthesize_perspectives
from theo.services.api.app.models.search import HybridSearchResult


@dataclass
class _StubRetrievalService:
    responses: dict[str, list[HybridSearchResult]]

    def __post_init__(self) -> None:
        self.requests: list[str | None] = []

    def search(self, _session, request):
        perspective = getattr(request.filters, "theological_tradition", None)
        self.requests.append(perspective)
        results = [item.model_copy() for item in self.responses.get(perspective, [])]
        return results, None


def _build_result(
    *,
    passage_id: str,
    document_id: str,
    snippet: str,
    document_title: str,
    score: float,
) -> HybridSearchResult:
    return HybridSearchResult(
        id=passage_id,
        document_id=document_id,
        text=snippet,
        osis_ref="John.20.1",
        start_char=0,
        end_char=len(snippet),
        score=score,
        snippet=snippet,
        rank=1,
        document_title=document_title,
    )


def test_synthesize_perspectives_builds_consensus_and_tensions() -> None:
    skeptical_result = _build_result(
        passage_id="skeptical-1",
        document_id="doc-s",
        snippet="Resurrection accounts diverge. Shared insight.",
        document_title="Skeptical Study",
        score=0.6,
    )
    apologetic_result = _build_result(
        passage_id="apologetic-1",
        document_id="doc-a",
        snippet="Shared insight. Harmonisation focuses on coherence.",
        document_title="Apologetic Survey",
        score=0.75,
    )
    neutral_result = _build_result(
        passage_id="neutral-1",
        document_id="doc-n",
        snippet="Shared insight. Balanced tone across sources.",
        document_title="Neutral Overview",
        score=0.5,
    )

    stub_service = _StubRetrievalService(
        {
            "skeptical": [skeptical_result],
            "apologetic": [apologetic_result],
            "neutral": [neutral_result],
        }
    )

    synthesis = synthesize_perspectives(
        "What happened at the resurrection?",
        session=None,  # session unused by stub
        retrieval_service=stub_service,  # type: ignore[arg-type]
        top_k=3,
    )

    assert stub_service.requests == ["skeptical", "apologetic", "neutral"]
    assert "Shared insight." in synthesis.consensus_points
    assert synthesis.tension_map["skeptical"] == ["Resurrection accounts diverge."]
    assert synthesis.perspective_views["apologetic"].citations
    assert "Shared insight" in synthesis.meta_analysis

