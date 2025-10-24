"""Modular AI service architecture for Theoria."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
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


__all__ = ["AIProvider", "BaseAIClient"]
