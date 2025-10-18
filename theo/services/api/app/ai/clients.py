"""Language model client abstractions and provider implementations."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import random
import time
from typing import Any, Protocol
import uuid

import httpx
from cachetools import LRUCache

from theo.application.ports.ai_registry import GenerationError


class LanguageModelClient(Protocol):
    """Common protocol implemented by provider-specific clients."""

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
        cache_key: str | None = None,
    ) -> str:
        """Return a text completion."""
        ...


def build_hypothesis_prompt(
    question: str,
    passages: Sequence[Mapping[str, Any] | Any],
    *,
    persona: str = "analyst",
    max_hypotheses: int = 4,
) -> str:
    """Craft a structured prompt for hypothesis generation workflows.

    The prompt mirrors the style used across RAG workflows: each passage is
    enumerated with an index, OSIS reference, and anchor context. The language
    model is instructed to respond with strictly formatted JSON to simplify
    downstream parsing.

    Args:
        question: The theological research question under review.
        passages: Retrieved passages or citation-like objects. Each item may
            either be a mapping (``dict``/``pydantic`` model) or any object
            exposing ``snippet``/``osis`` attributes. Unrecognised attributes
            default to empty strings so the prompt remains robust when fed
            heterogeneous retrieval payloads.
        persona: Optional persona hint (``analyst`` | ``skeptic`` |
            ``apologist`` | ``synthesizer``) which adjusts the framing given to
            the model.
        max_hypotheses: Upper bound on how many hypotheses the model should
            return.

    Returns:
        A formatted prompt ready for :class:`LanguageModelClient.generate`.
    """

    persona_descriptions = {
        "analyst": "Evaluate the evidence even-handedly and surface multiple competing explanations.",
        "skeptic": "Interrogate confident claims and highlight tensions in the evidence.",
        "apologist": "Explore ways the evidence could be harmonised without ignoring tensions.",
        "synthesizer": "Balance scholarly and pastoral perspectives when framing possibilities.",
    }
    persona_key = persona.lower()
    persona_instruction = persona_descriptions.get(
        persona_key,
        persona_descriptions["analyst"],
    )

    context_lines: list[str] = []
    for idx, raw in enumerate(passages, start=1):
        if isinstance(raw, Mapping):
            snippet = str(raw.get("snippet") or raw.get("text") or "").strip()
            osis = str(raw.get("osis") or raw.get("osis_ref") or "Unknown").strip()
            anchor = str(
                raw.get("anchor")
                or raw.get("page_no")
                or raw.get("meta", {}).get("page")
                or raw.get("meta", {}).get("anchor")
                or "context"
            ).strip()
            score = raw.get("score")
        else:
            snippet = str(getattr(raw, "snippet", getattr(raw, "text", ""))).strip()
            osis = str(
                getattr(raw, "osis", getattr(raw, "osis_ref", "Unknown"))
            ).strip()
            anchor = str(getattr(raw, "anchor", getattr(raw, "page_no", "context"))).strip()
            score = getattr(raw, "score", None)

        if not snippet:
            snippet = "[No snippet provided]"
        passage_line = f"[{idx}] {snippet} (OSIS {osis}, {anchor})"
        if isinstance(score, (int, float)):
            passage_line += f" — relevance {max(min(score, 1.0), 0.0):.2f}"
        context_lines.append(passage_line)

    if not context_lines:
        context_lines.append("[No passages retrieved]")

    instruction_block = "\n".join(
        [
            "You are Theo Engine's hypothesis {persona}.".format(
                persona=persona_key if persona_key in persona_descriptions else "analyst"
            ),
            persona_instruction,
            "Given the theological question and passages, generate {max_hypotheses} competing hypotheses.".format(
                max_hypotheses=max_hypotheses,
            ),
            "Each hypothesis must be testable, cite relevant passage indices, and include confidence (0-1).",
            "Respond **only** with JSON using this schema:",
            '{"hypotheses": ['
            '{"id": "string", "claim": "string", "confidence": 0-1, "supporting_indices": [int], "contradicting_indices": [int], "fallacy_notes": ["string"], "perspective_scores": {"apologetic": 0-1, "skeptical": 0-1, "neutral": 0-1}}'
            "]}",
        ]
    )

    prompt_parts = [instruction_block]
    prompt_parts.append(f"Question: {question.strip()}" if question.strip() else "Question: [unspecified]")
    prompt_parts.append("Passages:")
    prompt_parts.extend(context_lines)
    prompt_parts.append("Return JSON only. Do not include markdown fences or commentary.")

    return "\n".join(prompt_parts)


@dataclass
class AIClientSettings:
    """Runtime settings shared across AI clients."""

    request_timeout: float = 30.0
    read_timeout: float = 60.0
    total_timeout: float = 120.0
    max_attempts: int = 3
    backoff_initial: float = 1.0
    backoff_multiplier: float = 2.0
    backoff_max: float = 30.0
    jitter: float = 0.0
    retryable_statuses: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)
    user_agent: str = "Theoria-AIClient/1.0"
    log_metadata: dict[str, Any] = field(default_factory=lambda: {"component": "ai-client"})
    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("theo.services.api.ai.clients")
    )
    clock: Callable[[], float] = field(default_factory=lambda: time.monotonic)
    sleep: Callable[[float], None] = field(default_factory=lambda: time.sleep)
    cache_size: int = 256


DEFAULT_AI_CLIENT_SETTINGS = AIClientSettings()


class BaseAIClient:
    """Shared utilities for provider-specific clients."""

    def __init__(self, http_client: httpx.Client, settings: AIClientSettings | None = None) -> None:
        self._settings = settings or DEFAULT_AI_CLIENT_SETTINGS
        self._client = http_client
        self._cache: LRUCache[str, str] = LRUCache(maxsize=self._settings.cache_size)

    def close(self) -> None:
        """Release HTTP resources held by the underlying client."""

        self._client.close()

    def __enter__(self) -> "BaseAIClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _build_timeout(self, remaining_budget: float) -> httpx.Timeout:
        connect_timeout = min(self._settings.request_timeout, remaining_budget)
        read_timeout = min(self._settings.read_timeout, remaining_budget)
        minimal = 0.001
        connect_timeout = max(connect_timeout, minimal)
        read_timeout = max(read_timeout, minimal)
        return httpx.Timeout(connect_timeout, read=read_timeout)

    def _compute_backoff(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None:
            headers = response.headers
            header_value = headers.get("Retry-After")
            if header_value:
                parsed = self._parse_retry_after(header_value)
                if parsed is not None:
                    return parsed
            for key in ("retry-after-ms", "x-ms-retry-after-ms"):
                if key in headers:
                    try:
                        return max(float(headers[key]) / 1000.0, 0.0)
                    except (TypeError, ValueError):
                        continue
        delay = self._settings.backoff_initial * (self._settings.backoff_multiplier ** (attempt - 1))
        delay = min(delay, self._settings.backoff_max)
        if self._settings.jitter:
            spread = self._settings.jitter
            delay *= random.uniform(1 - spread, 1 + spread)
        return max(delay, 0.0)

    @staticmethod
    def _parse_retry_after(value: str) -> float | None:
        try:
            seconds = float(value)
            return max(seconds, 0.0)
        except (TypeError, ValueError):
            try:
                parsed_date = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return None
            if parsed_date is None:
                return None
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            now = datetime.now(tz=parsed_date.tzinfo)
            delta = (parsed_date - now).total_seconds()
            return max(delta, 0.0)

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        request_kwargs: dict[str, Any] | None = None,
        idempotency_headers: dict[str, str] | None = None,
        retryable_statuses: tuple[int, ...] | None = None,
    ) -> httpx.Response:
        settings = self._settings
        metadata = dict(settings.log_metadata)
        request_kwargs = dict(request_kwargs or {})
        headers = dict(request_kwargs.get("headers") or {})
        if settings.user_agent and not any(key.lower() == "user-agent" for key in headers):
            headers.setdefault("User-Agent", settings.user_agent)
        if idempotency_headers:
            headers.update(idempotency_headers)
        request_kwargs["headers"] = headers
        retry_statuses = retryable_statuses or settings.retryable_statuses

        start = settings.clock()
        budget = settings.total_timeout
        last_exception: Exception | None = None
        last_status_code: int | None = None

        for attempt in range(1, settings.max_attempts + 1):
            elapsed = settings.clock() - start
            remaining = budget - elapsed
            if remaining <= 0:
                raise GenerationError("Request timed out before completion")
            attempt_kwargs = dict(request_kwargs)
            attempt_kwargs["timeout"] = self._build_timeout(remaining)

            try:
                response = self._client.request(method, url, **attempt_kwargs)
            except httpx.TimeoutException as exc:  # pragma: no cover - exercised via unit tests
                last_exception = exc
                settings.logger.warning(
                    "AI request attempt timeout",
                    extra={
                        **metadata,
                        "attempt": attempt,
                        "method": method,
                        "url": url,
                    },
                )
                if attempt >= settings.max_attempts:
                    raise GenerationError("Request timed out") from exc
                delay = self._compute_backoff(attempt, None)
                delay = min(delay, max(remaining, 0.0))
                if delay > 0:
                    settings.sleep(delay)
                continue

            settings.logger.info(
                "AI request attempt",
                extra={
                    **metadata,
                    "attempt": attempt,
                    "method": method,
                    "url": url,
                    "status_code": response.status_code,
                },
            )

            if response.status_code < 400:
                return response

            if response.status_code not in retry_statuses or attempt >= settings.max_attempts:
                last_status_code = response.status_code
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise GenerationError(
                        f"HTTP {response.status_code}: {exc}",
                        status_code=response.status_code,
                        retryable=response.status_code in retry_statuses,
                    ) from exc
                raise GenerationError(
                    f"Unexpected response status: {response.status_code}",
                    status_code=response.status_code,
                )

            delay = self._compute_backoff(attempt, response)
            elapsed = settings.clock() - start
            remaining = budget - elapsed
            delay = min(delay, max(remaining, 0.0))
            if delay > 0:
                settings.sleep(delay)

        if last_exception is not None:
            raise GenerationError(
                f"Request failed after {settings.max_attempts} attempts",
                status_code=last_status_code,
                retryable=True,
            ) from last_exception
        raise GenerationError(
            f"Request failed without response after {settings.max_attempts} attempts",
            retryable=False,
        )

    @staticmethod
    def _create_http_client(
        *, base_url: str, headers: dict[str, str], settings: AIClientSettings
    ) -> httpx.Client:
        merged_headers = dict(headers)
        if settings.user_agent:
            merged_headers.setdefault("User-Agent", settings.user_agent)
        timeout = httpx.Timeout(settings.request_timeout, read=settings.read_timeout)
        return httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=merged_headers,
            timeout=timeout,
        )

@dataclass
class OpenAIConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    organization: str | None = None


class OpenAIClient(BaseAIClient):
    """Minimal OpenAI-compatible client using ``httpx``."""

    def __init__(
        self, config: OpenAIConfig, *, settings: AIClientSettings | None = None
    ) -> None:
        resolved_settings = settings or DEFAULT_AI_CLIENT_SETTINGS
        headers = {
            "Authorization": f"Bearer {config.api_key}",
        }
        if config.organization:
            headers["OpenAI-Organization"] = config.organization
        client = BaseAIClient._create_http_client(
            base_url=config.base_url,
            headers=headers,
            settings=resolved_settings,
        )
        super().__init__(client, resolved_settings)

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
        cache_key: str | None = None,
    ) -> str:
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]
        payload = {
            "model": model,
            "input": prompt,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }
        idempotency_key = cache_key or str(uuid.uuid4())
        response = self._request_with_retry(
            "POST",
            "/responses",
            request_kwargs={"json": payload},
            idempotency_headers={"Idempotency-Key": idempotency_key},
        )
        data = response.json()
        if "output" in data and isinstance(data["output"], list):
            # Responses API shape
            text_chunks = [chunk.get("content", "") for chunk in data["output"]]
            result = "".join(
                segment if isinstance(segment, str) else segment.get("text", "")
                for segment in text_chunks
            )
            if cache_key:
                self._cache[cache_key] = result
            return result
        if "choices" in data:
            choice = data["choices"][0]
            if "message" in choice:
                result = choice["message"].get("content", "")
                if cache_key:
                    self._cache[cache_key] = result
                return result
            if "text" in choice:
                result = choice["text"]
                if cache_key:
                    self._cache[cache_key] = result
                return result
        raise GenerationError(
            "Unexpected OpenAI response payload - missing expected fields",
            provider="openai",
        )


@dataclass
class AzureOpenAIConfig:
    api_key: str
    endpoint: str
    deployment: str
    api_version: str = "2024-02-15-preview"


class AzureOpenAIClient(BaseAIClient):
    """Azure-hosted OpenAI compatible client."""

    def __init__(
        self, config: AzureOpenAIConfig, *, settings: AIClientSettings | None = None
    ) -> None:
        self._deployment = config.deployment
        self._api_version = config.api_version
        resolved_settings = settings or DEFAULT_AI_CLIENT_SETTINGS
        client = BaseAIClient._create_http_client(
            base_url=config.endpoint,
            headers={"api-key": config.api_key},
            settings=resolved_settings,
        )
        super().__init__(client, resolved_settings)

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
        cache_key: str | None = None,
    ) -> str:
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        url = (
            f"/openai/deployments/{self._deployment}/chat/completions"
            f"?api-version={self._api_version}"
        )
        idempotency_key = cache_key or str(uuid.uuid4())
        response = self._request_with_retry(
            "POST",
            url,
            request_kwargs={"json": payload},
            idempotency_headers={"x-ms-client-request-id": idempotency_key},
        )
        data = response.json()
        if data.get("choices"):
            choice = data["choices"][0]
            if "message" in choice:
                result = choice["message"].get("content", "")
                if cache_key:
                    self._cache[cache_key] = result
                return result
        raise GenerationError(
            "Unexpected Azure OpenAI response payload - missing expected fields",
            provider="azure_openai",
        )


@dataclass
class AnthropicConfig:
    api_key: str
    base_url: str = "https://api.anthropic.com"
    version: str = "2023-06-01"


class AnthropicClient(BaseAIClient):
    """Anthropic Messages API client."""

    def __init__(
        self, config: AnthropicConfig, *, settings: AIClientSettings | None = None
    ) -> None:
        resolved_settings = settings or DEFAULT_AI_CLIENT_SETTINGS
        client = BaseAIClient._create_http_client(
            base_url=config.base_url.rstrip("/") + "/v1",
            headers={
                "x-api-key": config.api_key,
                "anthropic-version": config.version,
                "content-type": "application/json",
            },
            settings=resolved_settings,
        )
        super().__init__(client, resolved_settings)

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
        cache_key: str | None = None,
    ) -> str:
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]
        payload = {
            "model": model,
            "max_tokens": max_output_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        idempotency_key = cache_key or str(uuid.uuid4())
        response = self._request_with_retry(
            "POST",
            "/messages",
            request_kwargs={"json": payload},
            idempotency_headers={"anthropic-idempotency-key": idempotency_key},
        )
        data = response.json()
        content = data.get("content") or []
        if content and isinstance(content, list):
            first = content[0]
            if isinstance(first, dict):
                result = first.get("text", "")
                if cache_key:
                    self._cache[cache_key] = result
                return result
        raise GenerationError(
            "Unexpected Anthropic response payload - missing expected fields",
            provider="anthropic",
        )


@dataclass
class VertexAIConfig:
    project_id: str
    location: str
    model: str
    access_token: str
    base_url: str | None = None


class VertexAIClient(BaseAIClient):
    """Vertex AI prediction service client using REST calls."""

    def __init__(
        self, config: VertexAIConfig, *, settings: AIClientSettings | None = None
    ) -> None:
        base = config.base_url or f"https://{config.location}-aiplatform.googleapis.com"
        self._model = config.model
        self._project = config.project_id
        self._location = config.location
        resolved_settings = settings or DEFAULT_AI_CLIENT_SETTINGS
        client = BaseAIClient._create_http_client(
            base_url=base,
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Content-Type": "application/json",
            },
            settings=resolved_settings,
        )
        super().__init__(client, resolved_settings)

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
        cache_key: str | None = None,
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
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]
        idempotency_key = cache_key or str(uuid.uuid4())
        response = self._request_with_retry(
            "POST",
            endpoint,
            request_kwargs={"json": payload},
            idempotency_headers={"x-request-id": idempotency_key},
        )
        data = response.json()
        predictions = data.get("predictions") or []
        if predictions:
            first = predictions[0]
            if isinstance(first, dict):
                result = first.get("content", "") or first.get("output", "")
                if cache_key:
                    self._cache[cache_key] = result
                return result
            if isinstance(first, str):
                result = first
                if cache_key:
                    self._cache[cache_key] = result
                return result
        raise GenerationError(
            "Unexpected Vertex AI response payload - missing expected fields",
            provider="vertex_ai",
        )


@dataclass
class LocalVLLMConfig:
    base_url: str
    api_key: str | None = None


class LocalVLLMClient(BaseAIClient):
    """Client for self-hosted vLLM instances exposing the OpenAI API."""

    def __init__(
        self, config: LocalVLLMConfig, *, settings: AIClientSettings | None = None
    ) -> None:
        headers: dict[str, str] = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        resolved_settings = settings or DEFAULT_AI_CLIENT_SETTINGS
        client = BaseAIClient._create_http_client(
            base_url=config.base_url,
            headers=headers,
            settings=resolved_settings,
        )
        super().__init__(client, resolved_settings)

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
        cache_key: str | None = None,
    ) -> str:
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        idempotency_key = cache_key or str(uuid.uuid4())
        response = self._request_with_retry(
            "POST",
            "/v1/chat/completions",
            request_kwargs={"json": payload},
            idempotency_headers={"Idempotency-Key": idempotency_key},
        )
        data = response.json()
        if data.get("choices"):
            message = data["choices"][0].get("message", {})
            result = message.get("content", "")
            if cache_key:
                self._cache[cache_key] = result
            return result
        raise GenerationError(
            "Unexpected vLLM response payload - missing expected fields",
            provider="vllm",
        )


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
        cache_key: str | None = None,
    ) -> str:
        del model, temperature, max_output_tokens, cache_key  # Unused but part of the interface

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
            if not stripped.endswith(")"):
                continue

            index_close = stripped.find("]")
            if index_close <= 1:
                continue
            index_value = stripped[1:index_close].strip()
            remainder = stripped[index_close + 1 :].strip()
            if not index_value or not remainder:
                continue

            if remainder.count(" (OSIS ") != 1:
                continue
            snippet_part, metadata = remainder.rsplit(" (OSIS ", 1)
            snippet_value = snippet_part.strip()
            if not snippet_value or not metadata:
                continue

            if "," not in metadata:
                continue
            osis_part, anchor_part = metadata.split(",", 1)
            anchor_part = anchor_part.rstrip(")").strip()
            osis_value = osis_part.strip()
            if not osis_value or not anchor_part:
                continue

            passages.append(
                {
                    "index": index_value,
                    "snippet": snippet_value,
                    "osis": osis_value,
                    "anchor": anchor_part,
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


set_client_factory(build_client)


__all__ = [
    "AIClientSettings",
    "AnthropicClient",
    "AnthropicConfig",
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
