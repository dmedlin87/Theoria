"""Composite router for AI workflows split across dedicated modules."""

from __future__ import annotations

from fastapi import APIRouter

from . import chat, exports, generative, guardrails, llm, providers

router = APIRouter()
router.include_router(guardrails.router)
router.include_router(llm.router)
router.include_router(chat.router)
router.include_router(generative.router)
router.include_router(exports.router)

settings_router = providers.router

__all__ = ["router", "settings_router"]
