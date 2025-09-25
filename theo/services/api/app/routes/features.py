"""Feature flags and capability discovery endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from ..core.settings import get_settings

router = APIRouter()


@router.get("/", summary="List enabled feature flags")
def list_features() -> dict[str, bool]:
    settings = get_settings()
    return {
        "gpt5_codex_preview": getattr(settings, "gpt5_codex_preview_enabled", False),
        "job_tracking": True,
        "document_annotations": True,
        "ai_copilot": True,
    }
