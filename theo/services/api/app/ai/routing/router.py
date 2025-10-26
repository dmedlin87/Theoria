"""Thread-safe AI request router with request deduplication."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Dict, Optional

from time import perf_counter

from .. import BaseAIClient
from ..cache.cache_manager import CacheManager
from ..ledger.usage_tracker import UsageTracker
from theo.application.facades.telemetry import record_counter, record_histogram
from theo.application.telemetry import (
    LLM_INFERENCE_ERROR_METRIC,
    LLM_INFERENCE_LATENCY_METRIC,
    LLM_INFERENCE_REQUESTS_METRIC,
)

logger = logging.getLogger(__name__)


class SafeAIRouter:
    """Coordinate AI requests across multiple providers safely."""

    def __init__(
        self,
        clients: list[BaseAIClient],
        usage_tracker: Optional[UsageTracker] = None,
        cache_manager: Optional[CacheManager] = None,
    ) -> None:
        if not clients:
            raise ValueError("At least one AI client must be provided")

        self.clients = clients
        self.usage_tracker = usage_tracker or UsageTracker()
        self.cache_manager = cache_manager or CacheManager()

        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self._inflight_requests: Dict[str, asyncio.Future[str]] = {}

    @asynccontextmanager
    async def _get_request_lock(self, cache_key: str) -> AsyncIterator[None]:
        """Acquire a per-request lock to prevent duplicate work."""

        async with self._global_lock:
            lock = self._locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            yield

    async def execute_generation(
        self,
        prompt: str,
        model_hint: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Execute an AI generation request with deduplication and caching."""

        cache_key = self._build_cache_key(prompt, model_hint, **kwargs)

        cached = await self.cache_manager.get(cache_key)
        if cached is not None:
            logger.debug("Router cache hit for %s", cache_key)
            return cached

        async with self._global_lock:
            inflight = self._inflight_requests.get(cache_key)
            if inflight is not None:
                logger.debug("Awaiting in-flight request for %s", cache_key)
                return await inflight

            future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
            self._inflight_requests[cache_key] = future

        try:
            async with self._get_request_lock(cache_key):
                cached = await self.cache_manager.get(cache_key)
                if cached is not None:
                    logger.debug("Router cache hit after lock for %s", cache_key)
                    future = self._inflight_requests.pop(cache_key)
                    if not future.done():
                        future.set_result(cached)
                    return cached

                result = await self._generate_with_fallback(prompt, model_hint, **kwargs)
                await self.cache_manager.set(cache_key, result)

                future = self._inflight_requests.pop(cache_key)
                if not future.done():
                    future.set_result(result)
                return result
        except Exception as exc:
            logger.exception("Generation failed for %s", cache_key)
            future = self._inflight_requests.pop(cache_key, None)
            if future is not None and not future.done():
                future.set_exception(exc)
            raise

    async def _generate_with_fallback(
        self,
        prompt: str,
        model_hint: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Attempt generation using the preferred client with fallbacks."""

        primary_client = self._select_client(model_hint)
        providers_to_try = [primary_client] + [c for c in self.clients if c is not primary_client]

        last_error: Optional[Exception] = None
        for client in providers_to_try:
            wall_start: Optional[float] = None
            try:
                request_id = await self.usage_tracker.start_request(
                    client.get_provider(),
                    client.get_model_name(),
                )
                start_time = datetime.utcnow()
                wall_start = perf_counter()
                result = await client.complete(prompt, **kwargs)
                wall_duration = perf_counter() - wall_start
                duration = (datetime.utcnow() - start_time).total_seconds()
                self._record_inference_metrics(
                    client, wall_duration, status="success"
                )
                await self.usage_tracker.complete_request(
                    provider=client.get_provider(),
                    model=client.get_model_name(),
                    prompt_tokens=len(prompt.split()),
                    completion_tokens=len(result.split()),
                    duration=duration,
                    request_id=request_id,
                )
                return result
            except Exception as exc:  # pragma: no cover - exercised in integration paths
                wall_duration = (
                    perf_counter() - wall_start if wall_start is not None else 0.0
                )
                self._record_inference_metrics(
                    client, wall_duration, status="error"
                )
                logger.warning(
                    "AI client %s failed: %s", client.get_provider().value, exc
                )
                last_error = exc
                continue

        raise RuntimeError("All AI clients failed") from last_error

    def _select_client(self, model_hint: Optional[str]) -> BaseAIClient:
        """Select a client by model hint or fall back to the first client."""

        if model_hint:
            for client in self.clients:
                if model_hint.lower() in client.get_model_name().lower():
                    return client
        return self.clients[0]

    def _build_cache_key(self, prompt: str, model_hint: Optional[str], **kwargs: Any) -> str:
        """Create a deterministic cache key for a request."""

        normalized_kwargs = {k: kwargs[k] for k in sorted(kwargs)}
        payload = {
            "prompt": prompt,
            "model_hint": model_hint,
            "params": normalized_kwargs,
        }
        digest = hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()
        return digest[:16]

    async def clear_cache(self, older_than: Optional[timedelta] = None) -> None:
        """Clear the router cache, optionally pruning by age."""

        await self.cache_manager.clear(older_than=older_than)
        async with self._global_lock:
            self._inflight_requests.clear()
            self._locks.clear()

    def _record_inference_metrics(
        self, client: BaseAIClient, duration: float, *, status: str
    ) -> None:
        """Record latency and throughput metrics for an inference attempt."""

        provider = client.get_provider().value
        model = client.get_model_name()
        labels = {"provider": provider, "model": model, "status": status}
        record_histogram(
            LLM_INFERENCE_LATENCY_METRIC,
            value=duration,
            labels=labels,
        )
        record_counter(LLM_INFERENCE_REQUESTS_METRIC, labels=labels)
        if status == "error":
            record_counter(
                LLM_INFERENCE_ERROR_METRIC,
                labels={"provider": provider, "model": model},
            )


__all__ = ["SafeAIRouter"]
