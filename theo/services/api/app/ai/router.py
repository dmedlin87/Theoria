"""Routing service for language model selection and budget enforcement."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import logging
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
class _RoutingLedger:
    spend: defaultdict[str, float]
    latency: dict[str, float]
    lock: threading.Lock

    @classmethod
    def create(cls) -> "_RoutingLedger":
        return cls(defaultdict(float), {}, threading.Lock())


_LEDGER = _RoutingLedger.create()


LOGGER = logging.getLogger(__name__)


_DEFAULT_WARNING_RATIO = 0.8


_TRACER = trace.get_tracer("theo.router")


class LLMRouterService:
    """Selects LLM providers while respecting routing constraints."""

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
            latency_threshold = self._as_float(config.get("latency_threshold_ms"))
            if latency_threshold is not None:
                span.set_attribute("llm.latency_threshold", latency_threshold)
            warning_ratio = self._warning_ratio(config)

            with self._ledger.lock:
                spent = self._ledger.spend[model.name]
                span.set_attribute("llm.spent_before_call", spent)
                projected_spend = spent + estimated_cost
                last_latency = self._ledger.latency.get(model.name)
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
                    self._ledger.spend[model.name] = ceiling
                    error = GenerationError(
                        "Budget exhausted for model "
                        f"{model.name} (spent {spent:.2f} >= {ceiling:.2f})"
                    )
                    span.set_attribute("llm.budget_status", "precheck_blocked")
                    span.record_exception(error)
                    LOGGER.warning(
                        (
                            "Model %s (workflow %s) projected spend %.2f exceeded "
                            "ceiling %.2f before generation"
                        ),
                        model.name,
                        workflow,
                        projected_spend,
                        ceiling,
                    )
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
                raise error

            completion_tokens = max(len(output) // 4, 0) if isinstance(output, str) else 0
            cost = self._estimate_cost(model, prompt, output)
            with self._ledger.lock:
                spent = self._ledger.spend[model.name]
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
                    self._ledger.spend[model.name] = ceiling
                    error = GenerationError(
                        "Budget exhausted for model "
                        f"{model.name} (spent {spent + cost:.2f} > {ceiling:.2f})"
                    )
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
                self._ledger.spend[model.name] = total_spend

            span.set_attribute("llm.latency_ms", round(latency_ms, 2))
            span.set_attribute("llm.completion_tokens", completion_tokens)
            span.set_attribute("llm.cost", cost)
            span.set_attribute("llm.budget_status", "accepted")

            return RoutedGeneration(
                model=model, output=output, latency_ms=latency_ms, cost=cost
            )

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

    def _warning_ratio(self, config: dict[str, Any]) -> float:
        for key in ("threshold_warning_ratio", "warning_ratio"):
            ratio = self._as_float(config.get(key))
            if ratio is not None:
                return max(0.0, ratio)
        return _DEFAULT_WARNING_RATIO

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


__all__ = ["LLMRouterService", "RoutedGeneration", "get_router", "reset_router_state"]
