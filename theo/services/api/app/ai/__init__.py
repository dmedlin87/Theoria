"""Modular AI service architecture for Theoria."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from importlib import import_module
from typing import TYPE_CHECKING, Any, AsyncIterator

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


_REGISTRY_EXPORTS = (
    "GenerationError",
    "LLMModel",
    "LLMRegistry",
    "SECRET_CONFIG_KEYS",
    "SETTINGS_KEY",
    "get_llm_registry",
    "save_llm_registry",
)

_RAG_EXPORTS = (
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
)

_REGISTRY_EXPORT_SET = set(_REGISTRY_EXPORTS)
_RAG_EXPORT_SET = set(_RAG_EXPORTS)

if TYPE_CHECKING:  # pragma: no cover - only used for static analysis
    from .registry import (  # noqa: F401
        GenerationError,
        LLMModel,
        LLMRegistry,
        SECRET_CONFIG_KEYS,
        SETTINGS_KEY,
        get_llm_registry,
        save_llm_registry,
    )
    from .rag import (  # noqa: F401
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


def __getattr__(name: str) -> Any:
    """Lazily import registry and RAG helpers to avoid circular imports."""

    if name in _REGISTRY_EXPORT_SET:
        module = import_module(".registry", __name__)
        return getattr(module, name)
    if name in _RAG_EXPORT_SET:
        module = import_module(".rag", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Provide module attributes for introspection tools."""

    return sorted(set(globals()) | _REGISTRY_EXPORT_SET | _RAG_EXPORT_SET)


__all__ = [
    "AIProvider",
    "BaseAIClient",
    *_REGISTRY_EXPORTS,
    *_RAG_EXPORTS,
]


