"""Composite AI router package."""

from __future__ import annotations

from fastapi import APIRouter

from ...ai.registry import get_llm_registry
from ...analytics.topics import (
    TopicDigest,
    generate_topic_digest,
    store_topic_digest,
    upsert_digest_document,
)
from . import digest, watchlists, workflows

router = APIRouter()
router.include_router(workflows.router)
router.include_router(digest.router)
router.include_router(watchlists.router)

settings_router = workflows.settings_router

__all__ = [
    "router",
    "settings_router",
    "TopicDigest",
    "get_llm_registry",
    "generate_topic_digest",
    "store_topic_digest",
    "upsert_digest_document",
]



