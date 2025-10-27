"""Routing service for language model selection and budget enforcement."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Iterator

try:  # pragma: no cover - optional tracing dependency
    from opentelemetry import trace
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback used in tests
    class _NoopSpan:
        def __enter__(self):  # noqa: D401 - simple context manager interface
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def set_attribute(self, *_args, **_kwargs) -> None:
            return None

    class _NoopTracer:
        def start_as_current_span(self, *_args, **_kwargs):
            return _NoopSpan()

    class _NoopTraceModule:
        def get_tracer(self, *_args, **_kwargs) -> _NoopTracer:
            return _NoopTracer()

        def get_current_span(self) -> _NoopSpan:
            return _NoopSpan()

    trace = _NoopTraceModule()  # type: ignore[assignment]
from sqlalchemy.orm import Session

from theo.application.ports.ai_registry import GenerationError

from .ledger import CacheRecord, SharedLedger
from .registry import LLMModel, LLMRegistry, get_llm_registry

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter as _PrometheusCounter
except Exception:  # pragma: no cover - metrics disabled
    _PrometheusCounter = None  # type: ignore[assignment]


@dataclass
class RoutedGeneration:
    """Result returned after a successful routed generation."""

    model: LLMModel
    output: str
    latency_ms: float
    cost: float
    cache_hit: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class _CacheSettings:
    """Resolved cache configuration for the current workflow."""

    enabled: bool
    ttl_seconds: float
    max_entries: int


@dataclass
class _ModelHealth:
    """Tracks model health metrics for circuit breaker logic."""

    failure_count: int = 0
    last_failure_time: float | None = None
    last_success_time: float | None = None
    consecutive_failures: int = 0


_LEDGER = SharedLedger()


LOGGER = logging.getLogger(__name__)


_DEFAULT_WARNING_RATIO = 0.8


_TRACER = trace.get_tracer("theo.router")


class _NoopCounter:
    def labels(self, *args: object, **kwargs: object) -> "_NoopCounter":
        return self

    def inc(self, amount: float = 1.0) -> None:
        return None


if _PrometheusCounter is not None:  # pragma: no cover - exercised when metrics enabled
    _ROUTER_LEDGER_EVENTS = _PrometheusCounter(
        "theo_router_dedup_events_total",
        "Router deduplication events while coordinating inflight generations.",
        labelnames=("event",),
    )
else:  # pragma: no cover - metrics disabled
    _ROUTER_LEDGER_EVENTS = _NoopCounter()


def _record_router_ledger_event(event: str, **extra: object) -> None:
    LOGGER.debug("router.ledger.%s", event, extra=extra)
    try:
        _ROUTER_LEDGER_EVENTS.labels(event=event).inc()
    except Exception:  # pragma: no cover - defensive guard
        LOGGER.debug("failed to record router ledger metric", exc_info=True)


class LLMRouterService:
    """Selects LLM providers while respecting routing constraints."""

    DEFAULT_CACHE_TTL = 300.0
    DEFAULT_CACHE_MAX_ENTRIES = 128
    DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 3
    DEFAULT_CIRCUIT_BREAKER_TIMEOUT = 60.0
    DEFAULT_INFLIGHT_WAIT_TIMEOUT = 120.0
    DEFAULT_LATE_JOIN_WINDOW = 0.05

    def __init__(self, registry: LLMRegistry, ledger: SharedLedger | None = None) -> None:
        self.registry = registry
        self._ledger = ledger or _LEDGER
        self._model_health: dict[str, _ModelHealth] = {}
        self._tokenizer_cache: dict[str, Any] = {}
        # Allow timeout override for testing
        env_timeout = os.environ.get("THEO_ROUTER_INFLIGHT_TIMEOUT")
        self._inflight_timeout = float(env_timeout) if env_timeout else self.DEFAULT_INFLIGHT_WAIT_TIMEOUT
        env_late_join = os.environ.get("THEO_ROUTER_LATE_JOIN_WINDOW")
        self._late_join_window = float(env_late_join) if env_late_join else self.DEFAULT_LATE_JOIN_WINDOW

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
        reasoning_mode: str | None = None,
    ) -> RoutedGeneration:
        """Generate content using ``model`` if it meets routing constraints."""

        request_started_at = time.time()
        prompt_tokens = self._estimate_tokens(prompt, model.model)
        with _TRACER.start_as_current_span("router.execute_generation") as span:
            span.set_attribute("llm.workflow", workflow)
            span.set_attribute("llm.model_name", model.name)
            span.set_attribute("llm.model_id", model.model)
            span.set_attribute("llm.temperature", temperature)
            span.set_attribute("llm.max_output_tokens", max_output_tokens)
            span.set_attribute("llm.prompt_tokens", prompt_tokens)
            if reasoning_mode:
                span.set_attribute("llm.reasoning_mode", reasoning_mode)

            config = self._workflow_config(model, workflow)
            ceiling = self._as_float(config.get("spend_ceiling"))
            # Estimate cost with expected output tokens for more accurate budget projection
            estimated_completion_tokens = max_output_tokens
            estimated_cost = self._estimate_cost_from_tokens(
                model, prompt_tokens, estimated_completion_tokens
            )
            span.set_attribute("llm.estimated_cost", estimated_cost)
            if ceiling is not None:
                span.set_attribute("llm.budget_ceiling", ceiling)
            latency_threshold = self._as_float(config.get("latency_threshold_ms"))
            if latency_threshold is not None:
                span.set_attribute("llm.latency_threshold", latency_threshold)
            warning_ratio = self._warning_ratio(config)

            cache_settings = self._cache_settings(config)
            # Use content-based hashing for better cache key collision handling
            workflow_key = f"{workflow}:{reasoning_mode}" if reasoning_mode else workflow
            cache_key = self._generate_cache_key(
                model.name, workflow_key, prompt, temperature, max_output_tokens
            )
            cache_status = "bypass"
            now = time.monotonic()
            late_join = False

            stale_status: str | None = None
            wait_observed_updated_at: float | None = None
            with self._ledger.transaction() as txn:
                spent = txn.get_spend(model.name)
                span.set_attribute("llm.spent_before_call", spent)
                projected_spend = spent + estimated_cost
                last_latency = txn.get_latency(model.name)
                if (
                    ceiling is not None
                    and warning_ratio > 0.0
                    and ceiling > 0.0
                    and projected_spend >= ceiling * warning_ratio
                ):
                    LOGGER.warning(
                        (
                            "Model %s (workflow %s) projected spend %.2f is %.0f%% "
                            "of ceiling %.2f (current spend %.2f, estimated cost %.2f)"
                        ),
                        model.name,
                        workflow,
                        projected_spend,
                        warning_ratio * 100,
                        ceiling,
                        spent,
                        estimated_cost,
                    )
                if (
                    latency_threshold is not None
                    and last_latency is not None
                    and warning_ratio > 0.0
                    and latency_threshold > 0.0
                    and last_latency >= latency_threshold * warning_ratio
                ):
                    LOGGER.warning(
                        (
                            "Model %s (workflow %s) recent latency %.1fms is %.0f%% "
                            "of threshold %.1fms"
                        ),
                        model.name,
                        workflow,
                        last_latency,
                        warning_ratio * 100,
                        latency_threshold,
                    )
                if ceiling is not None and projected_spend >= ceiling:
                    txn.set_spend(model.name, ceiling)

                if cache_settings.enabled:
                    txn.purge_expired_cache(now, cache_settings.ttl_seconds)
                    cached_record = txn.get_cache_entry(cache_key)
                    if cached_record:
                        span.set_attribute("llm.cache_status", "hit")
                        result = self._record_to_generation(cached_record)
                        result.cache_hit = True
                        return result

                inflight = txn.get_inflight(cache_key)
                if inflight is None:
                    txn.create_inflight(
                        cache_key, model_name=model.name, workflow=workflow
                    )
                    cache_status = "miss" if cache_settings.enabled else "bypass"
                    owns_inflight = True
                    _record_router_ledger_event(
                        "acquired_inflight",
                        cache_key=cache_key,
                        model=model.name,
                        workflow=workflow,
                    )
                elif inflight.status == "waiting":
                    cache_status = "wait"
                    owns_inflight = False
                    wait_observed_updated_at = inflight.updated_at
                    if request_started_at - inflight.updated_at > self._late_join_window:
                        late_join = True
                    _record_router_ledger_event(
                        "dedup_waiting",
                        cache_key=cache_key,
                        model=model.name,
                        workflow=workflow,
                    )
                else:
                    stale_status = inflight.status
                    owns_inflight = False
                    wait_observed_updated_at = inflight.updated_at
                    _record_router_ledger_event(
                        "stale_row_detected",
                        cache_key=cache_key,
                        status=inflight.status,
                        model=model.name,
                        workflow=workflow,
                    )

            if not owns_inflight and stale_status is None:
                # Re-read after releasing the transaction to catch owners that
                # finished between the initial check and now.
                refreshed = self._ledger._read_inflight(cache_key)
                if refreshed is not None and refreshed.status != "waiting":
                    stale_status = refreshed.status
                    wait_observed_updated_at = refreshed.updated_at

            if stale_status is not None:
                _record_router_ledger_event(
                    "stale_row_wait",
                    cache_key=cache_key,
                    status=stale_status,
                    model=model.name,
                    workflow=workflow,
                )
                try:
                    self._ledger.wait_for_inflight(
                        cache_key, observed_updated_at=wait_observed_updated_at, timeout=self._inflight_timeout
                    )
                except GenerationError:
                    _record_router_ledger_event(
                        "stale_row_wait_error",
                        cache_key=cache_key,
                        status=stale_status,
                        model=model.name,
                        workflow=workflow,
                    )
                    pass
                else:
                    _record_router_ledger_event(
                        "stale_row_wait_complete",
                        cache_key=cache_key,
                        status=stale_status,
                        model=model.name,
                        workflow=workflow,
                    )
                with self._ledger.transaction() as txn:
                    txn.create_inflight(
                        cache_key, model_name=model.name, workflow=workflow
                    )
                _record_router_ledger_event(
                    "stale_row_reset",
                    cache_key=cache_key,
                    status=stale_status,
                    model=model.name,
                    workflow=workflow,
                )
                cache_status = "miss" if cache_settings.enabled else "bypass"
                owns_inflight = True

            if not owns_inflight:
                wait_cache_status = cache_status
                _record_router_ledger_event(
                    "wait_for_primary",
                    cache_key=cache_key,
                    status=wait_cache_status,
                    model=model.name,
                    workflow=workflow,
                )
                try:
                    record = self._ledger.wait_for_inflight(
                        cache_key, observed_updated_at=wait_observed_updated_at, timeout=self._inflight_timeout
                    )
                except GenerationError:
                    _record_router_ledger_event(
                        "wait_for_primary_error",
                        cache_key=cache_key,
                        status=wait_cache_status,
                        model=model.name,
                        workflow=workflow,
                    )
                    with self._ledger.transaction() as txn:
                        stale_row = txn.get_inflight(cache_key)
                        if stale_row is not None:
                            wait_observed_updated_at = stale_row.updated_at
                        txn.create_inflight(
                            cache_key, model_name=model.name, workflow=workflow
                        )
                    cache_status = "miss" if cache_settings.enabled else "bypass"
                    owns_inflight = True
                    span.set_attribute("llm.cache_status", cache_status)
                else:
                    if late_join:
                        _record_router_ledger_event(
                            "wait_for_primary_late_join",
                            cache_key=cache_key,
                            status=wait_cache_status,
                            model=model.name,
                            workflow=workflow,
                        )
                        with self._ledger.transaction() as txn:
                            txn.create_inflight(
                                cache_key, model_name=model.name, workflow=workflow
                            )
                        cache_status = "miss" if cache_settings.enabled else "bypass"
                        owns_inflight = True
                        span.set_attribute("llm.cache_status", cache_status)
                        late_join = False
                    else:
                        _record_router_ledger_event(
                            "wait_for_primary_complete",
                            cache_key=cache_key,
                            status=wait_cache_status,
                            model=model.name,
                            workflow=workflow,
                        )
                        span.set_attribute("llm.cache_status", wait_cache_status)
                        return self._record_to_generation(record)

            span.set_attribute("llm.cache_status", cache_status)

            try:
                with self._ledger.transaction() as txn:
                    spent = txn.get_spend(model.name)
                    span.set_attribute("llm.spent_before_call", spent)
                    if ceiling is not None and spent + estimated_cost >= ceiling:
                        txn.set_spend(model.name, ceiling)
                        error = GenerationError(
                            "Budget exhausted for model "
                            f"{model.name} (spent {spent:.2f} >= {ceiling:.2f})"
                        )
                        txn.mark_inflight_error(cache_key, str(error))
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
                    with self._ledger.transaction() as txn:
                        txn.mark_inflight_error(cache_key, str(exc))
                    raise

                latency_ms = (time.perf_counter() - start) * 1000.0
                latency_threshold = self._as_float(config.get("latency_threshold_ms"))
                with self._ledger.transaction() as txn:
                    txn.set_latency(model.name, latency_ms)
                if (
                    latency_threshold is not None
                    and warning_ratio > 0.0
                    and latency_threshold > 0.0
                    and latency_ms >= latency_threshold * warning_ratio
                ):
                    LOGGER.warning(
                        (
                            "Model %s (workflow %s) latency %.1fms is %.0f%% of "
                            "threshold %.1fms"
                        ),
                        model.name,
                        workflow,
                        latency_ms,
                        warning_ratio * 100,
                        latency_threshold,
                    )
                if latency_threshold is not None and latency_ms > latency_threshold:
                    error = GenerationError(
                        "Latency threshold exceeded for model "
                        f"{model.name}: {latency_ms:.1f}ms > {latency_threshold:.1f}ms"
                    )
                    span.set_attribute("llm.latency_threshold", latency_threshold)
                    span.set_attribute("llm.latency_ms", round(latency_ms, 2))
                    span.record_exception(error)
                    LOGGER.warning(
                        (
                            "Model %s (workflow %s) latency %.1fms exceeded threshold %.1fms"
                        ),
                        model.name,
                        workflow,
                        latency_ms,
                        latency_threshold,
                    )
                    with self._ledger.transaction() as txn:
                        txn.mark_inflight_error(cache_key, str(error))
                    raise error

                completion_tokens = 0
                cost = 0.0
                error_after_generation: GenerationError | None = None
                with self._ledger.transaction() as txn:
                    completion_tokens = (
                        self._estimate_tokens(output, model.model) if isinstance(output, str) else 0
                    )
                    cost = self._estimate_cost_from_tokens(
                        model, prompt_tokens, completion_tokens
                    )
                    spent = txn.get_spend(model.name)
                    total_spend = spent + cost
                    if (
                        ceiling is not None
                        and warning_ratio > 0.0
                        and ceiling > 0.0
                        and total_spend >= ceiling * warning_ratio
                    ):
                        LOGGER.warning(
                            (
                                "Model %s (workflow %s) spend %.2f is %.0f%% of ceiling %.2f "
                                "after generation"
                            ),
                            model.name,
                            workflow,
                            total_spend,
                            warning_ratio * 100,
                            ceiling,
                        )
                    if ceiling is not None and total_spend >= ceiling:
                        txn.set_spend(model.name, ceiling)
                        error = GenerationError(
                            "Budget exhausted for model "
                            f"{model.name} (spent {total_spend:.2f} >= {ceiling:.2f})"
                        )
                        txn.mark_inflight_error(cache_key, str(error))
                        span.set_attribute("llm.budget_status", "postcheck_blocked")
                        span.record_exception(error)
                        LOGGER.warning(
                            (
                                "Model %s (workflow %s) spend %.2f exceeded ceiling %.2f after "
                                "generation"
                            ),
                            model.name,
                            workflow,
                            total_spend,
                            ceiling,
                        )
                        error_after_generation = error
                    else:
                        txn.set_spend(model.name, total_spend)
                        txn.mark_inflight_success(
                            cache_key,
                            model_name=model.name,
                            workflow=workflow,
                            output=output if isinstance(output, str) else str(output),
                            latency_ms=latency_ms,
                            cost=cost,
                        )
                        if cache_settings.enabled:
                            current = time.monotonic()
                            txn.purge_expired_cache(current, cache_settings.ttl_seconds)
                            while txn.cache_size() >= cache_settings.max_entries:
                                txn.pop_oldest_cache_entry()
                            txn.store_cache_entry(
                                CacheRecord(
                                    cache_key=cache_key,
                                    model_name=model.name,
                                    workflow=workflow,
                                    prompt=prompt,
                                    temperature=float(temperature),
                                    max_output_tokens=int(max_output_tokens),
                                    output=output if isinstance(output, str) else str(output),
                                    latency_ms=latency_ms,
                                    cost=cost,
                                    created_at=current,
                                )
                            )

                if error_after_generation is not None:
                    raise error_after_generation

                span.set_attribute("llm.latency_ms", round(latency_ms, 2))
                span.set_attribute("llm.completion_tokens", completion_tokens)
                span.set_attribute("llm.cost", cost)
                span.set_attribute("llm.budget_status", "accepted")

                # Record success for circuit breaker
                self._record_model_success(model.name)

                return RoutedGeneration(
                    model=model,
                    output=output,
                    latency_ms=latency_ms,
                    cost=cost,
                    cache_hit=False,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
            except GenerationError as exc:
                # Record failure for circuit breaker
                self._record_model_failure(model.name)
                with self._ledger.transaction() as txn:
                    txn.mark_inflight_error(cache_key, str(exc))
                raise
            except Exception as exc:
                # Record failure for circuit breaker on unexpected errors
                self._record_model_failure(model.name)
                with self._ledger.transaction() as txn:
                    txn.mark_inflight_error(cache_key, str(exc))
                raise

    # ------------------------------------------------------------------
    # Introspection utilities
    # ------------------------------------------------------------------
    def get_spend(self, model_name: str) -> float:
        with self._ledger.transaction() as txn:
            return txn.get_spend(model_name)

    def get_latency(self, model_name: str) -> float | None:
        with self._ledger.transaction() as txn:
            return txn.get_latency(model_name)

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

        # Check circuit breaker
        if not self._check_circuit_breaker(model.name, config):
            return False

        with self._ledger.transaction() as txn:
            if ceiling is not None and txn.get_spend(model.name) >= ceiling:
                return False
            if latency_threshold is not None:
                last_latency = txn.get_latency(model.name)
                if last_latency is not None and last_latency > latency_threshold:
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

    def _warning_ratio(self, config: dict[str, Any]) -> float:
        for key in ("threshold_warning_ratio", "warning_ratio"):
            ratio = self._as_float(config.get(key))
            if ratio is not None:
                return max(0.0, ratio)
        return _DEFAULT_WARNING_RATIO

    def _check_circuit_breaker(self, model_name: str, config: dict[str, Any]) -> bool:
        """Check if model is available based on circuit breaker state."""
        health = self._model_health.get(model_name)
        if health is None:
            return True

        threshold = self._as_float(config.get("circuit_breaker_threshold")) or self.DEFAULT_CIRCUIT_BREAKER_THRESHOLD
        timeout = self._as_float(config.get("circuit_breaker_timeout_s")) or self.DEFAULT_CIRCUIT_BREAKER_TIMEOUT

        if health.consecutive_failures >= threshold:
            if health.last_failure_time is not None:
                elapsed = time.time() - health.last_failure_time
                if elapsed < timeout:
                    LOGGER.warning(
                        "Model %s circuit breaker open (failures: %d, elapsed: %.1fs)",
                        model_name,
                        health.consecutive_failures,
                        elapsed,
                    )
                    return False
                # Reset after timeout
                health.consecutive_failures = 0
        return True

    def _record_model_success(self, model_name: str) -> None:
        """Record successful model generation."""
        if model_name not in self._model_health:
            self._model_health[model_name] = _ModelHealth()
        health = self._model_health[model_name]
        health.last_success_time = time.time()
        health.consecutive_failures = 0

    def _record_model_failure(self, model_name: str) -> None:
        """Record failed model generation."""
        if model_name not in self._model_health:
            self._model_health[model_name] = _ModelHealth()
        health = self._model_health[model_name]
        health.failure_count += 1
        health.consecutive_failures += 1
        health.last_failure_time = time.time()
        LOGGER.warning(
            "Model %s failure recorded (consecutive: %d, total: %d)",
            model_name,
            health.consecutive_failures,
            health.failure_count,
        )

    def _estimate_tokens(self, text: str, model_name: str | None = None) -> int:
        """Estimate token count for text using tiktoken or fallback."""
        if not text:
            return 0

        fallback_estimate = max(len(text) // 4, 0)

        try:
            import tiktoken

            # Determine encoding based on model
            encoding_name = "cl100k_base"  # default for gpt-4, gpt-3.5-turbo
            if model_name:
                if "gpt-4" in model_name.lower():
                    encoding_name = "cl100k_base"
                elif "gpt-3.5" in model_name.lower():
                    encoding_name = "cl100k_base"
                elif "davinci" in model_name.lower() or "curie" in model_name.lower():
                    encoding_name = "p50k_base"

            if encoding_name not in self._tokenizer_cache:
                try:
                    self._tokenizer_cache[encoding_name] = tiktoken.get_encoding(encoding_name)
                except Exception:
                    # Fall back to cl100k_base if specific encoding fails
                    self._tokenizer_cache[encoding_name] = tiktoken.get_encoding("cl100k_base")

            encoder = self._tokenizer_cache[encoding_name]
            token_count = len(encoder.encode(text, disallowed_special=()))
            return max(token_count, fallback_estimate)
        except Exception:
            # Fallback to character-based estimation
            return fallback_estimate
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
        """Legacy cost estimation method - prefer _estimate_cost_from_tokens."""
        prompt_tokens = self._estimate_tokens(prompt, model.model)
        completion_tokens = self._estimate_tokens(completion, model.model) if completion else 0
        return self._estimate_cost_from_tokens(model, prompt_tokens, completion_tokens)

    def _estimate_cost_from_tokens(
        self, model: LLMModel, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Calculate cost from token counts using model pricing."""
        pricing = getattr(model, "pricing", {}) or {}
        per_call = self._as_float(pricing.get("per_call"))
        cost = per_call or 0.0
        prompt_rate = self._as_float(pricing.get("prompt_tokens"))
        completion_rate = self._as_float(pricing.get("completion_tokens"))
        if prompt_rate:
            cost += (prompt_tokens / 1000.0) * prompt_rate
        if completion_rate:
            cost += (completion_tokens / 1000.0) * completion_rate
        return cost

    def _generate_cache_key(
        self, model_name: str, workflow: str, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Generate a stable cache key using content hashing."""
        # Use SHA256 for content-based hashing to avoid collisions
        content = f"{model_name}:{workflow}:{temperature}:{max_tokens}:{prompt}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]

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

    def _record_to_generation(self, record: CacheRecord) -> RoutedGeneration:
        model = self.registry.models.get(record.model_name)
        if model is None:
            raise GenerationError(f"Unknown model in ledger cache: {record.model_name}")
        return RoutedGeneration(
            model=model,
            output=record.output,
            latency_ms=record.latency_ms,
            cost=record.cost,
        )

def get_router(session: Session, registry: LLMRegistry | None = None) -> LLMRouterService:
    """Return a router service backed by the shared ledger."""

    if registry is None:
        registry = get_llm_registry(session)
    return LLMRouterService(registry, ledger=_LEDGER)


def reset_router_state() -> None:
    """Reset routing telemetry (used by tests)."""

    _LEDGER.reset()


__all__ = ["LLMRouterService", "RoutedGeneration", "get_router", "reset_router_state"]
