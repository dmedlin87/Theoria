"""Client implementations for the modular AI stack."""
from __future__ import annotations

from ..legacy_clients import (
    AIClientSettings,
    AnthropicClient,
    AnthropicConfig,
    AzureOpenAIClient,
    AzureOpenAIConfig,
    DEFAULT_AI_CLIENT_SETTINGS,
    EchoClient,
    GenerationError,
    LanguageModelClient,
    LocalVLLMClient,
    LocalVLLMConfig,
    OpenAIClient,
    OpenAIConfig,
    VertexAIClient,
    VertexAIConfig,
    build_client,
    build_hypothesis_prompt,
)
from .anthropic_client import AnthropicClient as AsyncAnthropicClient
from .factory import AIClientFactory
from .openai_client import OpenAIClient as AsyncOpenAIClient

__all__ = [
    "AIClientFactory",
    "AIClientSettings",
    "AnthropicClient",
    "AnthropicConfig",
    "AsyncAnthropicClient",
    "AsyncOpenAIClient",
    "AzureOpenAIClient",
    "AzureOpenAIConfig",
    "DEFAULT_AI_CLIENT_SETTINGS",
    "EchoClient",
    "GenerationError",
    "LanguageModelClient",
    "LocalVLLMClient",
    "LocalVLLMConfig",
    "OpenAIClient",
    "OpenAIConfig",
    "VertexAIClient",
    "VertexAIConfig",
    "build_client",
    "build_hypothesis_prompt",
]
