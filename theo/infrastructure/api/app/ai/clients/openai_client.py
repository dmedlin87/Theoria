"""OpenAI client implementation for the modular AI stack."""
from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Optional

from .. import AIProvider, BaseAIClient

try:  # pragma: no cover - import guarded for optional dependency
    import openai
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    openai = None  # type: ignore


class OpenAIClient(BaseAIClient):
    """Asynchronous OpenAI chat completion client."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        organization: Optional[str] = None,
        extra_client_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required")

        self.api_key = api_key
        self.model = model
        self.organization = organization
        self.extra_client_kwargs = extra_client_kwargs or {}
        self._client: Optional["openai.AsyncOpenAI"] = None

    @property
    def client(self) -> "openai.AsyncOpenAI":
        """Lazily instantiate the OpenAI client."""

        if openai is None:  # pragma: no cover - defensive guard
            raise RuntimeError("openai package is not installed")

        if self._client is None:
            kwargs: Dict[str, Any] = {"api_key": self.api_key, **self.extra_client_kwargs}
            if self.organization:
                kwargs["organization"] = self.organization
            self._client = openai.AsyncOpenAI(**kwargs)
        return self._client

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion using the configured model."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.choices[0].message.content or ""

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Stream a completion response as tokens arrive."""

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content

    def get_provider(self) -> AIProvider:
        return AIProvider.OPENAI

    def get_model_name(self) -> str:
        return self.model


__all__ = ["OpenAIClient"]
