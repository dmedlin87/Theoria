"""Routing service for language model selection and budget enforcement."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Iterator

from opentelemetry import trace
from sqlalchemy.orm import Session

from .clients import GenerationError
from .ledger import CacheRecord, SharedLedger
from .registry import LLMModel, LLMRegistry, get_llm_registry


@dataclass
class RoutedGeneration:
    """Result returned after a successful routed generation."""

    model: LLMModel
    output: str
    latency_ms: float
    cost: float


@dataclass
class _CacheSettings:
    """Resolved cache configuration for the current workflow."""

    enabled: bool
    ttl_seconds: float
    max_entries: int


_LEDGER = SharedLedger()


LOGGER = logging.getLogger(__name__)


_DEFAULT_WARNING_RATIO = 0.8


_TRACER = trace.get_tracer("theo.router")


class LLMRouterService:
    """Selects LLM providers while respecting routing constraints."""

    DEFAULT_CACHE_TTL = 300.0
    DEFAULT_CACHE_MAX_ENTRIES = 128

    def __init__(self, registry: LLMRegistry, ledger: SharedLedger | None = None) -> None:
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
            latency_threshold = self._as_float(config.get("latency_threshold_ms"))
            if latency_threshold is not None:
                span.set_attribute("llm.latency_threshold", latency_threshold)
            warning_ratio = self._warning_ratio(config)

            cache_settings = self._cache_settings(config)
            cache_key = self._ledger.encode_cache_key(
                (model.name, workflow, prompt, float(temperature), int(max_output_tokens))
            )
            cache_status = "bypass"
            now = time.monotonic()

            stale_status: str | None = None
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
                if ceiling is not None and projected_spend > ceiling:
                    txn.set_spend(model.name, ceiling)

                if cache_settings.enabled:
                    txn.purge_expired_cache(now, cache_settings.ttl_seconds)
                    cached_record = txn.get_cache_entry(cache_key)
                    if cached_record:
                        span.set_attribute("llm.cache_status", "hit")
                        return self._record_to_generation(cached_record)

                inflight = txn.get_inflight(cache_key)
                if inflight is None:
                    txn.create_inflight(
                        cache_key, model_name=model.name, workflow=workflow
                    )
                    cache_status = "miss" if cache_settings.enabled else "bypass"
                    owns_inflight = True
                elif inflight.status == "waiting":
                    cache_status = "wait"
                    owns_inflight = False
                else:
                    stale_status = inflight.status
                    owns_inflight = False

            if stale_status is not None:
                try:
                    self._ledger.wait_for_inflight(cache_key)
                except GenerationError:
                    pass
                with self._ledger.transaction() as txn:
                    txn.create_inflight(
                        cache_key, model_name=model.name, workflow=workflow
                    )
                cache_status = "miss" if cache_settings.enabled else "bypass"
                owns_inflight = True

            if not owns_inflight:
                span.set_attribute("llm.cache_status", cache_status)
                record = self._ledger.wait_for_inflight(cache_key)
                return self._record_to_generation(record)

            span.set_attribute("llm.cache_status", cache_status)

            try:
                with self._ledger.transaction() as txn:
                    spent = txn.get_spend(model.name)
                    span.set_attribute("llm.spent_before_call", spent)
                    if ceiling is not None and spent + estimated_cost > ceiling:
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

                completion_tokens = (
                    max(len(output) // 4, 0) if isinstance(output, str) else 0
                )
                cost = self._estimate_cost(model, prompt, output)
                with self._ledger.transaction() as txn:
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
                    if ceiling is not None and total_spend > ceiling:
                        txn.set_spend(model.name, ceiling)
                        error = GenerationError(
                            "Budget exhausted for model "
                            f"{model.name} (spent {total_spend:.2f} > {ceiling:.2f})"
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
                        raise error
                    txn.set_spend(model.name, total_spend)

                span.set_attribute("llm.latency_ms", round(latency_ms, 2))
                span.set_attribute("llm.completion_tokens", completion_tokens)
                span.set_attribute("llm.cost", cost)
                span.set_attribute("llm.budget_status", "accepted")

                generation = RoutedGeneration(
                    model=model, output=output, latency_ms=latency_ms, cost=cost
                )

                with self._ledger.transaction() as txn:
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

                return generation
            except Exception as exc:
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
