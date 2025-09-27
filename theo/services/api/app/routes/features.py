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
        "cross_references": True,
        "textual_variants": True,
        "morphology": True,
        "commentaries": True,
        "verse_timeline": getattr(settings, "verse_timeline_enabled", False),
    }


@router.get("/discovery", summary="Structured discovery metadata")
def discovery() -> dict[str, dict[str, bool]]:
    settings = get_settings()
    return {
        "features": {
            "research": True,
            "contradictions": getattr(settings, "contradictions_enabled", False),
            "geo": getattr(settings, "geo_enabled", False),
            "cross_references": True,
            "textual_variants": True,
            "morphology": True,
            "commentaries": True,
            "creator_verse_perspectives": getattr(
                settings, "creator_verse_perspectives_enabled", False
            ),
            "verse_timeline": getattr(settings, "verse_timeline_enabled", False),
        }
    }
