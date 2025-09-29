"""Routing service for language model selection and budget enforcement."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import threading
import time
from typing import Any, Iterator

from opentelemetry import trace
from sqlalchemy.orm import Session

from .clients import GenerationError
from .registry import LLMModel, LLMRegistry, get_llm_registry


@dataclass
class RoutedGeneration:
    """Result returned after a successful routed generation."""

    model: LLMModel
    output: str
    latency_ms: float
    cost: float


@dataclass
class _CacheEntry:
    """Cached routed generation along with its creation timestamp."""

    generation: RoutedGeneration
    created_at: float


@dataclass
class _InflightRecord:
    """Tracks an in-flight generation so callers can wait for completion."""

    event: threading.Event
    result: RoutedGeneration | None = None
    error: Exception | None = None


@dataclass
class _CacheSettings:
    """Resolved cache configuration for the current workflow."""

    enabled: bool
    ttl_seconds: float
    max_entries: int


@dataclass
class _RoutingLedger:
    spend: defaultdict[str, float]
    latency: dict[str, float]
    lock: threading.Lock
    cache: dict[tuple[str, str, str, float, int], _CacheEntry]
    inflight: dict[tuple[str, str, str, float, int], _InflightRecord]

    @classmethod
    def create(cls) -> "_RoutingLedger":
        return cls(defaultdict(float), {}, threading.Lock(), {}, {})


_LEDGER = _RoutingLedger.create()


_TRACER = trace.get_tracer("theo.router")


class LLMRouterService:
    """Selects LLM providers while respecting routing constraints."""

    DEFAULT_CACHE_TTL = 300.0
    DEFAULT_CACHE_MAX_ENTRIES = 128

    def __init__(self, registry: LLMRegistry, ledger: _RoutingLedger | None = None) -> None:
        self.registry = registry
        self._ledger = ledger or _LEDGER

    # ------------------------------------------------------------------
    # Candidate selection
    # ------------------------------------------------------------------
    def iter_candidates(self, workflow: str, model_hint: str | None = None) -> Iterator[LLMModel]:
        """Yield viable models ordered by routing weight."""

        seen: set[str] = set()
        if model_hint and model_hint in self.registry.models:
            hinted = self.registry.models[model_hint]
            if self._is_available(hinted, workflow):
                seen.add(hinted.name)
                yield hinted
            else:
                seen.add(hinted.name)

        weighted: list[tuple[float, LLMModel]] = []
        for model in self.registry.models.values():
            if model.name in seen:
                continue
            config = self._workflow_config(model, workflow)
            weight = self._as_float(config.get("weight")) or 1.0
            weighted.append((weight, model))
        weighted.sort(key=lambda item: (item[0], item[1].name), reverse=True)

        for _, model in weighted:
            if self._is_available(model, workflow):
                yield model

    # ------------------------------------------------------------------
    # Generation execution
    # ------------------------------------------------------------------
    def execute_generation(
        self,
        *,
        workflow: str,
        model: LLMModel,
        prompt: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
    ) -> RoutedGeneration:
        """Generate content using ``model`` if it meets routing constraints."""

        prompt_tokens = max(len(prompt) // 4, 0)
        with _TRACER.start_as_current_span("router.execute_generation") as span:
            span.set_attribute("llm.workflow", workflow)
            span.set_attribute("llm.model_name", model.name)
            span.set_attribute("llm.model_id", model.model)
            span.set_attribute("llm.temperature", temperature)
            span.set_attribute("llm.max_output_tokens", max_output_tokens)
            span.set_attribute("llm.prompt_tokens", prompt_tokens)

            config = self._workflow_config(model, workflow)
            ceiling = self._as_float(config.get("spend_ceiling"))
            estimated_cost = self._estimate_cost(model, prompt, None)
            span.set_attribute("llm.estimated_cost", estimated_cost)
            if ceiling is not None:
                span.set_attribute("llm.budget_ceiling", ceiling)

            cache_settings = self._cache_settings(config)
            cache_key = (model.name, workflow, prompt, float(temperature), int(max_output_tokens))
            cache_status = "bypass"
            now = time.monotonic()
            record: _InflightRecord | None

            with self._ledger.lock:
                if cache_settings.enabled:
                    self._purge_expired_cache(now, cache_settings.ttl_seconds)
                    cached = self._ledger.cache.get(cache_key)
                    if cached:
                        span.set_attribute("llm.cache_status", "hit")
                        return cached.generation

                record = self._ledger.inflight.get(cache_key)
                if record is None:
                    record = _InflightRecord(threading.Event())
                    self._ledger.inflight[cache_key] = record
                    cache_status = "miss" if cache_settings.enabled else "bypass"
                else:
                    cache_status = "wait"

            assert record is not None  # For type-checkers

            if cache_status == "wait":
                span.set_attribute("llm.cache_status", cache_status)
                record.event.wait()
                if record.error is not None:
                    raise record.error
                if record.result is None:
                    raise GenerationError("Deduplicated generation completed without a result")
                return record.result

            span.set_attribute("llm.cache_status", cache_status)

            try:
                with self._ledger.lock:
                    spent = self._ledger.spend[model.name]
                    span.set_attribute("llm.spent_before_call", spent)
                    if ceiling is not None and spent + estimated_cost > ceiling:
                        self._ledger.spend[model.name] = ceiling
                        error = GenerationError(
                            "Budget exhausted for model "
                            f"{model.name} (spent {spent:.2f} >= {ceiling:.2f})"
                        )
                        span.set_attribute("llm.budget_status", "precheck_blocked")
                        span.record_exception(error)
                        raise error

                client = model.build_client()
                start = time.perf_counter()
                try:
                    output = client.generate(
                        prompt=prompt,
                        model=model.model,
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                    )
                except Exception as exc:  # pragma: no cover - propagate client errors
                    span.record_exception(exc)
                    raise

                latency_ms = (time.perf_counter() - start) * 1000.0
                with self._ledger.lock:
                    self._ledger.latency[model.name] = latency_ms
                latency_threshold = self._as_float(config.get("latency_threshold_ms"))
                if latency_threshold is not None and latency_ms > latency_threshold:
                    error = GenerationError(
                        "Latency threshold exceeded for model "
                        f"{model.name}: {latency_ms:.1f}ms > {latency_threshold:.1f}ms"
                    )
                    span.set_attribute("llm.latency_threshold", latency_threshold)
                    span.set_attribute("llm.latency_ms", round(latency_ms, 2))
                    span.record_exception(error)
                    raise error

                completion_tokens = max(len(output) // 4, 0) if isinstance(output, str) else 0
                cost = self._estimate_cost(model, prompt, output)
                with self._ledger.lock:
                    spent = self._ledger.spend[model.name]
                    if ceiling is not None and spent + cost > ceiling:
                        self._ledger.spend[model.name] = ceiling
                        error = GenerationError(
                            "Budget exhausted for model "
                            f"{model.name} (spent {spent + cost:.2f} > {ceiling:.2f})"
                        )
                        span.set_attribute("llm.budget_status", "postcheck_blocked")
                        span.record_exception(error)
                        raise error
                    self._ledger.spend[model.name] = spent + cost

                span.set_attribute("llm.latency_ms", round(latency_ms, 2))
                span.set_attribute("llm.completion_tokens", completion_tokens)
                span.set_attribute("llm.cost", cost)
                span.set_attribute("llm.budget_status", "accepted")

                generation = RoutedGeneration(
                    model=model, output=output, latency_ms=latency_ms, cost=cost
                )

            except Exception as exc:
                with self._ledger.lock:
                    record.error = exc
                    record.event.set()
                    self._ledger.inflight.pop(cache_key, None)
                raise

            with self._ledger.lock:
                record.result = generation
                if cache_settings.enabled:
                    self._purge_expired_cache(time.monotonic(), cache_settings.ttl_seconds)
                    self._store_cache_entry(cache_key, generation, cache_settings)
                record.event.set()
                self._ledger.inflight.pop(cache_key, None)

            return generation

    # ------------------------------------------------------------------
    # Introspection utilities
    # ------------------------------------------------------------------
    def get_spend(self, model_name: str) -> float:
        with self._ledger.lock:
            return self._ledger.spend.get(model_name, 0.0)

    def get_latency(self, model_name: str) -> float | None:
        with self._ledger.lock:
            return self._ledger.latency.get(model_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _workflow_config(self, model: LLMModel, workflow: str) -> dict[str, Any]:
        routing = dict(model.routing)
        overrides = routing.get("workflows")
        if isinstance(overrides, dict):
            specific = overrides.get(workflow)
            if isinstance(specific, dict):
                merged = {k: v for k, v in routing.items() if k != "workflows"}
                merged.update(specific)
                return merged
        return routing

    def _is_available(self, model: LLMModel, workflow: str) -> bool:
        config = self._workflow_config(model, workflow)
        ceiling = self._as_float(config.get("spend_ceiling"))
        latency_threshold = self._as_float(config.get("latency_threshold_ms"))
        with self._ledger.lock:
            if ceiling is not None and self._ledger.spend.get(model.name, 0.0) >= ceiling:
                return False
            if (
                latency_threshold is not None
                and self._ledger.latency.get(model.name, 0.0) > latency_threshold
            ):
                return False
        return True

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        return None

    def _estimate_cost(
        self, model: LLMModel, prompt: str, completion: str | None
    ) -> float:
        pricing = getattr(model, "pricing", {}) or {}
        per_call = self._as_float(pricing.get("per_call"))
        cost = per_call or 0.0
        prompt_rate = self._as_float(pricing.get("prompt_tokens"))
        completion_rate = self._as_float(pricing.get("completion_tokens"))
        if prompt_rate:
            prompt_tokens = max(len(prompt) // 4, 0)
            cost += (prompt_tokens / 1000.0) * prompt_rate
        if completion is not None and completion_rate:
            completion_tokens = max(len(completion) // 4, 0)
            cost += (completion_tokens / 1000.0) * completion_rate
        return cost

    def _cache_settings(self, config: dict[str, Any]) -> _CacheSettings:
        ttl_raw = self._as_float(config.get("cache_ttl_seconds"))
        ttl_seconds = float(ttl_raw) if ttl_raw and ttl_raw > 0 else 0.0

        max_entries_raw = self._as_float(config.get("cache_max_entries"))
        max_entries = int(max_entries_raw) if max_entries_raw and max_entries_raw > 0 else 0

        enabled_flag = self._as_bool(config.get("cache_enabled"))
        if enabled_flag is None:
            enabled = ttl_seconds > 0 or max_entries > 0
        else:
            enabled = enabled_flag

        if not enabled:
            return _CacheSettings(enabled=False, ttl_seconds=0.0, max_entries=0)

        if ttl_seconds <= 0:
            ttl_seconds = self.DEFAULT_CACHE_TTL
        if max_entries <= 0:
            max_entries = self.DEFAULT_CACHE_MAX_ENTRIES

        return _CacheSettings(enabled=True, ttl_seconds=ttl_seconds, max_entries=max_entries)

    def _purge_expired_cache(self, now: float, ttl: float) -> None:
        if ttl <= 0:
            return
        expired_keys = [
            key for key, entry in self._ledger.cache.items() if now - entry.created_at > ttl
        ]
        for key in expired_keys:
            self._ledger.cache.pop(key, None)

    def _store_cache_entry(
        self,
        key: tuple[str, str, str, float, int],
        generation: RoutedGeneration,
        settings: _CacheSettings,
    ) -> None:
        if not settings.enabled:
            return
        if settings.max_entries <= 0:
            return
        while len(self._ledger.cache) >= settings.max_entries:
            oldest_key, _ = min(
                self._ledger.cache.items(), key=lambda item: item[1].created_at
            )
            self._ledger.cache.pop(oldest_key, None)
        self._ledger.cache[key] = _CacheEntry(generation=generation, created_at=time.monotonic())


def get_router(session: Session, registry: LLMRegistry | None = None) -> LLMRouterService:
    """Return a router service backed by the shared ledger."""

    if registry is None:
        registry = get_llm_registry(session)
    return LLMRouterService(registry, ledger=_LEDGER)


def reset_router_state() -> None:
    """Reset routing telemetry (used by tests)."""

    with _LEDGER.lock:
        _LEDGER.spend.clear()
        _LEDGER.latency.clear()
        _LEDGER.cache.clear()
        _LEDGER.inflight.clear()


__all__ = ["LLMRouterService", "RoutedGeneration", "get_router", "reset_router_state"]
