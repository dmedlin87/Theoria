"""Modular AI service architecture for Theoria.

This package exposes the new Phase 2 AI modules while maintaining backwards
compatible accessors for the legacy ``theo.services.api.app.ai`` namespace.
Existing call sites still import helpers such as ``run_guarded_chat`` and the
guardrailed workflow responses directly from this package, so we intentionally
re-export the RAG layer and commonly consumed submodules here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from importlib import import_module
from typing import Any, AsyncIterator


class AIProvider(Enum):
    """Supported AI provider identifiers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    VERTEX = "vertex"
    LOCAL = "local"


class BaseAIClient(ABC):
    """Abstract base class for all AI provider clients."""

    @abstractmethod
    async def complete(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion for the given prompt."""

    @abstractmethod
    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Stream a completion for the given prompt."""

    @abstractmethod
    def get_provider(self) -> AIProvider:
        """Return the AI provider type."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the active model name."""


from . import rag as rag
from .rag import (
    CollaborationResponse,
    ComparativeAnalysisResponse,
    CorpusCurationReport,
    DevotionalResponse,
    GuardrailError,
    MultimediaDigestResponse,
    RAGAnswer,
    RAGCitation,
    SermonPrepResponse,
    VerseCopilotResponse,
    build_guardrail_refusal,
    build_sermon_deliverable,
    build_transcript_deliverable,
    generate_comparative_analysis,
    generate_devotional_flow,
    generate_multimedia_digest,
    generate_sermon_prep_outline,
    generate_verse_brief,
    record_used_citation_feedback,
    run_corpus_curation,
    run_guarded_chat,
    run_research_reconciliation,
    search_passages,
)

# Backwards compatibility ---------------------------------------------------
# Keep historically imported submodules addressable from the package root so
# ``from theo.services.api.app.ai import digest_service`` (and similar imports)
# continue to work during the incremental migration away from models.ai.
digest_service = import_module(".digest_service", __name__)
memory_index = import_module(".memory_index", __name__)
passage = import_module(".passage", __name__)
research_loop = import_module(".research_loop", __name__)
router = import_module(".router", __name__)
trails = import_module(".trails", __name__)
trails_memory_bridge = import_module(".trails_memory_bridge", __name__)


__all__ = [
    "AIProvider",
    "BaseAIClient",
    "CollaborationResponse",
    "ComparativeAnalysisResponse",
    "CorpusCurationReport",
    "DevotionalResponse",
    "GuardrailError",
    "MultimediaDigestResponse",
    "RAGAnswer",
    "RAGCitation",
    "SermonPrepResponse",
    "VerseCopilotResponse",
    "build_guardrail_refusal",
    "build_sermon_deliverable",
    "build_transcript_deliverable",
    "digest_service",
    "generate_comparative_analysis",
    "generate_devotional_flow",
    "generate_multimedia_digest",
    "generate_sermon_prep_outline",
    "generate_verse_brief",
    "memory_index",
    "passage",
    "rag",
    "record_used_citation_feedback",
    "research_loop",
    "router",
    "run_corpus_curation",
    "run_guarded_chat",
    "run_research_reconciliation",
    "search_passages",
    "trails",
    "trails_memory_bridge",
]
