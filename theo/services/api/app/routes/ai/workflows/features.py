"""Feature discovery routes for AI workflows."""

from __future__ import annotations

from fastapi import APIRouter

from theo.services.api.app.ai.guardrails import (
    AIFeaturesResponse,
    DEFAULT_GUARDRAIL_SETTINGS,
)

router = APIRouter()


@router.get("/features", response_model=AIFeaturesResponse)
def list_ai_features() -> AIFeaturesResponse:
    """Expose guardrail catalogues for client selection."""

    return AIFeaturesResponse(guardrails=DEFAULT_GUARDRAIL_SETTINGS)


__all__ = ["router", "list_ai_features"]
