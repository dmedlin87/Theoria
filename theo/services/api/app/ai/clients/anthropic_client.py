"""Anthropic Claude client implementation."""
from __future__ import annotations

from typing import Any, AsyncIterator, Optional

from .. import AIProvider, BaseAIClient

try:  # pragma: no cover - optional dependency support
    import anthropic
except ModuleNotFoundError:  # pragma: no cover - handled gracefully at runtime
    anthropic = None  # type: ignore


class AnthropicClient(BaseAIClient):
    """Adapter for Anthropic's Claude async client."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022") -> None:
        if not api_key:
            raise ValueError("Anthropic API key is required")

        self.api_key = api_key
        self.model = model
        self._client: Optional["anthropic.AsyncAnthropic"] = None

    @property
    def client(self) -> "anthropic.AsyncAnthropic":
        """Return a lazily-instantiated Anthropic client."""

        if anthropic is None:  # pragma: no cover - dependency missing guard
            raise RuntimeError("anthropic package is not installed")

        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        """Request a completion from Claude."""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", 4096),
            messages=[{"role": "user", "content": prompt}],
        )
        # Anthropic responses provide a list of content blocks.
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                return text
        return ""

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Stream Claude completions chunk-by-chunk."""

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", 4096),
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield text

    def get_provider(self) -> AIProvider:
        return AIProvider.ANTHROPIC

    def get_model_name(self) -> str:
        return self.model


__all__ = ["AnthropicClient"]
