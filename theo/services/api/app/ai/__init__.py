"""Modular AI service architecture for Theoria."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncIterator

from .rag import (
    ComparativeAnalysisResponse,
    DevotionalResponse,
    MultimediaDigestResponse,
    RAGAnswer,
    RAGCitation,
    SermonPrepResponse,
    VerseCopilotResponse,
    build_guardrail_refusal,
    build_sermon_deliverable,
    build_sermon_prep_package,
    build_transcript_deliverable,
    build_transcript_package,
    generate_comparative_analysis,
    generate_devotional_flow,
    generate_multimedia_digest,
    generate_sermon_prep_outline,
    generate_verse_brief,
    run_corpus_curation,
    run_guarded_chat,
    run_research_reconciliation,
)
from .registry import (
    GenerationError,
    LLMModel,
    LLMRegistry,
    SECRET_CONFIG_KEYS,
    SETTINGS_KEY,
    get_llm_registry,
    save_llm_registry,
)


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


__all__ = [
    "AIProvider",
    "BaseAIClient",
    "GenerationError",
    "LLMModel",
    "LLMRegistry",
    "SECRET_CONFIG_KEYS",
    "SETTINGS_KEY",
    "get_llm_registry",
    "save_llm_registry",
    "ComparativeAnalysisResponse",
    "DevotionalResponse",
    "MultimediaDigestResponse",
    "RAGAnswer",
    "RAGCitation",
    "SermonPrepResponse",
    "VerseCopilotResponse",
    "build_guardrail_refusal",
    "build_sermon_deliverable",
    "build_sermon_prep_package",
    "build_transcript_deliverable",
    "build_transcript_package",
    "generate_comparative_analysis",
    "generate_devotional_flow",
    "generate_multimedia_digest",
    "generate_sermon_prep_outline",
    "generate_verse_brief",
    "run_corpus_curation",
    "run_guarded_chat",
    "run_research_reconciliation",
]
