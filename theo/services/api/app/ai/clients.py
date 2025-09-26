"""Language model client abstractions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


class GenerationError(RuntimeError):
    """Raised when a provider fails to generate content."""


class LanguageModelClient(Protocol):
    """Common protocol implemented by provider-specific clients."""

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
    ) -> str:
        """Return a text completion."""


@dataclass
class OpenAIConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    organization: str | None = None


class OpenAIClient:
    """Minimal OpenAI-compatible client using ``httpx``."""

    def __init__(self, config: OpenAIConfig) -> None:
        headers = {
            "Authorization": f"Bearer {config.api_key}",
        }
        if config.organization:
            headers["OpenAI-Organization"] = config.organization
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(30.0, read=60.0),
        )

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
    ) -> str:
        payload = {
            "model": model,
            "input": prompt,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }
        response = self._client.post("/responses", json=payload)
        try:
            response.raise_for_status()
        except (
            httpx.HTTPStatusError
        ) as exc:  # pragma: no cover - network errors are rare in tests
            raise GenerationError(str(exc)) from exc
        data = response.json()
        if "output" in data and isinstance(data["output"], list):
            # Responses API shape
            text_chunks = [chunk.get("content", "") for chunk in data["output"]]
            return "".join(
                segment if isinstance(segment, str) else segment.get("text", "")
                for segment in text_chunks
            )
        if "choices" in data:
            choice = data["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "")
            if "text" in choice:
                return choice["text"]
        raise GenerationError("Unexpected OpenAI response payload")


class EchoClient:
    """Deterministic offline client that echoes provided context."""

    def __init__(self, suffix: str = "") -> None:
        self._suffix = suffix

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.0,
        max_output_tokens: int = 400,
    ) -> str:
        return f"{prompt.strip()}\n\n{self._suffix}".strip()


def build_client(provider: str, config: dict[str, str]) -> LanguageModelClient:
    """Instantiate a client for ``provider`` using ``config``."""

    normalized = provider.lower()
    if normalized == "openai":
        api_key = config.get("api_key")
        if not api_key:
            raise GenerationError("OpenAI provider requires an api_key")
        base_url = config.get("base_url") or "https://api.openai.com/v1"
        organization = config.get("organization")
        return OpenAIClient(
            OpenAIConfig(api_key=api_key, base_url=base_url, organization=organization)
        )
    if normalized in {"echo", "builtin", "mock"}:
        return EchoClient(config.get("suffix", ""))
    raise GenerationError(f"Unsupported provider: {provider}")


__all__ = [
    "EchoClient",
    "GenerationError",
    "LanguageModelClient",
    "OpenAIClient",
    "OpenAIConfig",
    "build_client",
]
