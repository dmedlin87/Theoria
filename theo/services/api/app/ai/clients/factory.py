"""Factory utilities for instantiating AI clients."""
from __future__ import annotations

from typing import Any, Dict

from .. import AIProvider, BaseAIClient
from .anthropic_client import AnthropicClient
from .openai_client import OpenAIClient


class AIClientFactory:
    """Factory responsible for building AI clients based on configuration."""

    _DEFAULT_MODELS = {
        AIProvider.OPENAI: "gpt-4",
        AIProvider.ANTHROPIC: "claude-3-5-sonnet-20241022",
    }

    @classmethod
    def create_client(cls, provider: AIProvider, config: Dict[str, Any]) -> BaseAIClient:
        """Create an AI client for the given provider."""

        if provider == AIProvider.OPENAI:
            return OpenAIClient(
                api_key=config["api_key"],
                model=config.get("model", cls._DEFAULT_MODELS[AIProvider.OPENAI]),
                organization=config.get("organization"),
                extra_client_kwargs=config.get("client_kwargs"),
            )
        if provider == AIProvider.ANTHROPIC:
            return AnthropicClient(
                api_key=config["api_key"],
                model=config.get("model", cls._DEFAULT_MODELS[AIProvider.ANTHROPIC]),
            )

        raise ValueError(f"Unsupported AI provider: {provider.value}")


__all__ = ["AIClientFactory"]
