"""Language model client abstractions and provider implementations."""

from __future__ import annotations

from dataclasses import dataclass
import re
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
        ...


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
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network errors are rare in tests
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


@dataclass
class AzureOpenAIConfig:
    api_key: str
    endpoint: str
    deployment: str
    api_version: str = "2024-02-15-preview"


class AzureOpenAIClient:
    """Azure-hosted OpenAI compatible client."""

    def __init__(self, config: AzureOpenAIConfig) -> None:
        self._deployment = config.deployment
        self._api_version = config.api_version
        self._client = httpx.Client(
            base_url=config.endpoint.rstrip("/"),
            headers={"api-key": config.api_key},
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
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        url = (
            f"/openai/deployments/{self._deployment}/chat/completions"
            f"?api-version={self._api_version}"
        )
        response = self._client.post(url, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network errors are rare in tests
            raise GenerationError(str(exc)) from exc
        data = response.json()
        if data.get("choices"):
            choice = data["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "")
        raise GenerationError("Unexpected Azure OpenAI response payload")


@dataclass
class AnthropicConfig:
    api_key: str
    base_url: str = "https://api.anthropic.com"
    version: str = "2023-06-01"


class AnthropicClient:
    """Anthropic Messages API client."""

    def __init__(self, config: AnthropicConfig) -> None:
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/") + "/v1",
            headers={
                "x-api-key": config.api_key,
                "anthropic-version": config.version,
                "content-type": "application/json",
            },
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
            "max_tokens": max_output_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = self._client.post("/messages", json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network errors are rare in tests
            raise GenerationError(str(exc)) from exc
        data = response.json()
        content = data.get("content") or []
        if content and isinstance(content, list):
            first = content[0]
            if isinstance(first, dict):
                return first.get("text", "")
        raise GenerationError("Unexpected Anthropic response payload")


@dataclass
class VertexAIConfig:
    project_id: str
    location: str
    model: str
    access_token: str
    base_url: str | None = None


class VertexAIClient:
    """Vertex AI prediction service client using REST calls."""

    def __init__(self, config: VertexAIConfig) -> None:
        base = config.base_url or f"https://{config.location}-aiplatform.googleapis.com"
        self._model = config.model
        self._project = config.project_id
        self._location = config.location
        self._client = httpx.Client(
            base_url=base.rstrip("/"),
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Content-Type": "application/json",
            },
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
        endpoint = (
            "/v1/projects/"
            f"{self._project}/locations/{self._location}/publishers/google/models/"
            f"{self._model}:predict"
        )
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
            },
        }
        response = self._client.post(endpoint, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network errors are rare in tests
            raise GenerationError(str(exc)) from exc
        data = response.json()
        predictions = data.get("predictions") or []
        if predictions:
            first = predictions[0]
            if isinstance(first, dict):
                return first.get("content", "") or first.get("output", "")
            if isinstance(first, str):
                return first
        raise GenerationError("Unexpected Vertex AI response payload")


@dataclass
class LocalVLLMConfig:
    base_url: str
    api_key: str | None = None


class LocalVLLMClient:
    """Client for self-hosted vLLM instances exposing the OpenAI API."""

    def __init__(self, config: LocalVLLMConfig) -> None:
        headers: dict[str, str] = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
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
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        response = self._client.post("/v1/chat/completions", json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network errors are rare in tests
            raise GenerationError(str(exc)) from exc
        data = response.json()
        if data.get("choices"):
            message = data["choices"][0].get("message", {})
            return message.get("content", "")
        raise GenerationError("Unexpected vLLM response payload")


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
        del model, temperature, max_output_tokens  # Unused but part of the interface

        normalized_prompt = prompt.replace("\\n", "\n")

        passages: list[dict[str, str]] = []
        in_passages = False
        for line in normalized_prompt.splitlines():
            stripped = line.strip()
            if not in_passages:
                if stripped == "Passages:":
                    in_passages = True
                continue
            if not stripped or not stripped.startswith("["):
                break
            match = re.match(
                r"^\[(?P<index>\d+)]\s+(?P<snippet>.+?)\s*\(OSIS\s+(?P<osis>[^,]+),\s*(?P<anchor>[^)]+)\)\s*$",
                stripped,
            )
            if not match:
                continue
            passages.append(
                {
                    "index": match.group("index"),
                    "snippet": match.group("snippet").strip(),
                    "osis": match.group("osis").strip(),
                    "anchor": match.group("anchor").strip(),
                }
            )

        if not passages:
            body = normalized_prompt.strip()
            if self._suffix:
                return f"{body}\n\n{self._suffix}".strip()
            return body

        summary_segments: list[str] = []
        for passage in passages:
            snippet = passage["snippet"]
            if snippet and snippet[-1] not in ".!?":
                snippet = f"{snippet}."
            summary_segments.append(f"[{passage['index']}] {snippet}")
        summary_text = " ".join(summary_segments)

        summary_block = summary_text.strip()
        if self._suffix:
            summary_block = f"{summary_block}\n\n{self._suffix}".strip()

        sources_entries = [
            f"[{passage['index']}] {passage['osis']} ({passage['anchor']})"
            for passage in passages
        ]
        sources_text = "\n".join(sources_entries)
        return f"{summary_block}\n\nSources: {sources_text}".strip()


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
    if normalized in {"azure", "azure_openai"}:
        api_key = config.get("api_key")
        endpoint = config.get("endpoint")
        deployment = config.get("deployment")
        if not api_key or not endpoint or not deployment:
            raise GenerationError(
                "Azure OpenAI provider requires api_key, endpoint, and deployment"
            )
        api_version = config.get("api_version", "2024-02-15-preview")
        return AzureOpenAIClient(
            AzureOpenAIConfig(
                api_key=api_key,
                endpoint=endpoint,
                deployment=deployment,
                api_version=api_version,
            )
        )
    if normalized == "anthropic":
        api_key = config.get("api_key")
        if not api_key:
            raise GenerationError("Anthropic provider requires an api_key")
        base_url = config.get("base_url", "https://api.anthropic.com")
        version = config.get("version", "2023-06-01")
        return AnthropicClient(
            AnthropicConfig(api_key=api_key, base_url=base_url, version=version)
        )
    if normalized in {"vertex", "vertex_ai", "google"}:
        project_id = config.get("project_id")
        location = config.get("location")
        model_name = config.get("model") or config.get("model_id")
        access_token = config.get("access_token")
        if not project_id or not location or not model_name or not access_token:
            raise GenerationError(
                "Vertex AI provider requires project_id, location, model/model_id, and access_token"
            )
        base_url = config.get("base_url")
        return VertexAIClient(
            VertexAIConfig(
                project_id=project_id,
                location=location,
                model=model_name,
                access_token=access_token,
                base_url=base_url,
            )
        )
    if normalized in {"vllm", "local", "local_vllm"}:
        base_url = config.get("base_url")
        if not base_url:
            raise GenerationError("vLLM provider requires a base_url")
        api_key = config.get("api_key")
        return LocalVLLMClient(LocalVLLMConfig(base_url=base_url, api_key=api_key))
    if normalized in {"echo", "builtin", "mock"}:
        return EchoClient(config.get("suffix", ""))
    raise GenerationError(f"Unsupported provider: {provider}")


__all__ = [
    "AnthropicClient",
    "AnthropicConfig",
    "AzureOpenAIClient",
    "AzureOpenAIConfig",
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
]
