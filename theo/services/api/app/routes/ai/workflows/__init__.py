"""Composable router for AI workflows."""

from __future__ import annotations

from fastapi import APIRouter

from . import chat, exports, features, flows, llm, settings
from .guardrails import (
    DEFAULT_REFUSAL_MESSAGE,
    extract_refusal_text,
    guardrail_advisory,
    guardrail_http_exception,
)

router = APIRouter()
router.include_router(features.router)
router.include_router(chat.router)
router.include_router(llm.router)
router.include_router(exports.router)
router.include_router(flows.router)

settings_router = settings.router

__all__ = [
    "router",
    "settings_router",
    "DEFAULT_REFUSAL_MESSAGE",
    "guardrail_http_exception",
    "guardrail_advisory",
    "extract_refusal_text",
]
