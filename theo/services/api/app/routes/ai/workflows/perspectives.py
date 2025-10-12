"""Perspective synthesis workflow endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session
from ....ai.reasoning import synthesize_perspectives
from ....ai.reasoning.perspectives import PerspectiveCitation, PerspectiveView
from ....models.ai import (
    PerspectiveCitationModel,
    PerspectiveSynthesisRequest,
    PerspectiveSynthesisResponse,
    PerspectiveViewModel,
)
from ....services.retrieval_service import (
    RetrievalService,
    get_retrieval_service,
)

router = APIRouter()


def _serialise_citation(citation: PerspectiveCitation) -> PerspectiveCitationModel:
    return PerspectiveCitationModel(
        document_id=citation.document_id,
        document_title=citation.document_title,
        osis=citation.osis,
        snippet=citation.snippet,
        rank=citation.rank,
        score=citation.score,
    )


def _serialise_view(view: PerspectiveView) -> PerspectiveViewModel:
    clamped_confidence = max(0.0, min(1.0, view.confidence))
    return PerspectiveViewModel(
        perspective=view.perspective,
        answer=view.answer,
        confidence=clamped_confidence,
        key_claims=list(view.key_claims),
        citations=[_serialise_citation(item) for item in view.citations],
    )


@router.post(
    "/perspectives",
    response_model=PerspectiveSynthesisResponse,
    response_model_exclude_none=True,
)
def run_perspective_synthesis(
    payload: PerspectiveSynthesisRequest,
    session: Session = Depends(get_session),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> PerspectiveSynthesisResponse:
    """Execute the multi-perspective retrieval workflow."""

    synthesis = synthesize_perspectives(
        payload.question,
        session,
        retrieval_service=retrieval_service,
        base_filters=payload.filters,
        top_k=payload.top_k,
    )

    views = {
        name: _serialise_view(view)
        for name, view in synthesis.perspective_views.items()
    }

    return PerspectiveSynthesisResponse(
        question=payload.question,
        consensus_points=synthesis.consensus_points,
        tension_map=synthesis.tension_map,
        meta_analysis=synthesis.meta_analysis,
        perspective_views=views,
    )


__all__ = ["router", "run_perspective_synthesis"]

