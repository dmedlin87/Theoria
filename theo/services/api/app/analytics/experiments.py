"""Utilities for recording search experiment outcomes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol, Sequence

from ..models.search import HybridSearchResult

LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - MLflow is optional at runtime
    import mlflow  # type: ignore[import]
except Exception:  # pragma: no cover - graceful degradation when unavailable
    mlflow = None  # type: ignore[assignment]


class ExperimentAnalyticsSink(Protocol):
    """Protocol implemented by analytics backends for experiment logging."""

    def record_reranker_outcome(self, outcome: "RerankerExperimentOutcome") -> None:
        """Persist the supplied reranker experiment outcome."""


@dataclass(slots=True)
class RerankerExperimentOutcome:
    """Summary of an individual reranker experiment run."""

    experiment: str
    strategy: str
    ordering_changed: bool
    rank_deltas: dict[str, int]
    score_deltas: dict[str, float]
    metadata: dict[str, Any]


def _rank_lookup(results: Sequence[HybridSearchResult]) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for index, result in enumerate(results, start=1):
        identifier = str(getattr(result, "id", ""))
        if not identifier:
            continue
        rank = getattr(result, "rank", None)
        lookup[identifier] = int(rank) if rank is not None else index
    return lookup


def _score_lookup(results: Sequence[HybridSearchResult]) -> dict[str, float]:
    lookup: dict[str, float] = {}
    for result in results:
        identifier = str(getattr(result, "id", ""))
        if not identifier:
            continue
        score = getattr(result, "score", None)
        lookup[identifier] = float(score) if score is not None else 0.0
    return lookup


def summarise_reranker_outcome(
    *,
    experiment: str,
    strategy: str,
    baseline: Sequence[HybridSearchResult],
    variant: Sequence[HybridSearchResult],
    metadata: Mapping[str, Any] | None = None,
) -> RerankerExperimentOutcome:
    """Build a :class:`RerankerExperimentOutcome` from baseline and variant results."""

    metadata_dict: dict[str, Any] = {
        "baseline_size": len(baseline),
        "variant_size": len(variant),
    }
    if metadata:
        metadata_dict.update(metadata)

    baseline_ranks = _rank_lookup(baseline)
    variant_ranks = _rank_lookup(variant)
    rank_deltas: dict[str, int] = {}
    for identifier, baseline_rank in baseline_ranks.items():
        variant_rank = variant_ranks.get(identifier)
        if variant_rank is None:
            continue
        rank_deltas[identifier] = baseline_rank - variant_rank

    baseline_scores = _score_lookup(baseline)
    variant_scores = _score_lookup(variant)
    score_deltas: dict[str, float] = {}
    for identifier, baseline_score in baseline_scores.items():
        variant_score = variant_scores.get(identifier)
        if variant_score is None:
            continue
        score_deltas[identifier] = baseline_score - variant_score

    ordering_changed = [
        str(getattr(result, "id", ""))
        for result in baseline
        if getattr(result, "id", None) is not None
    ] != [
        str(getattr(result, "id", ""))
        for result in variant
        if getattr(result, "id", None) is not None
    ]

    return RerankerExperimentOutcome(
        experiment=experiment,
        strategy=strategy,
        ordering_changed=ordering_changed,
        rank_deltas=rank_deltas,
        score_deltas=score_deltas,
        metadata=metadata_dict,
    )


class LoggingExperimentAnalyticsSink:
    """Default analytics sink that emits structured logs (and optional MLflow metrics)."""

    def record_reranker_outcome(self, outcome: RerankerExperimentOutcome) -> None:
        LOGGER.info(
            "search.reranker_experiment",
            extra={
                "event": "search.reranker_experiment",
                "experiment": outcome.experiment,
                "strategy": outcome.strategy,
                "ordering_changed": outcome.ordering_changed,
                "rank_deltas": outcome.rank_deltas,
                "score_deltas": outcome.score_deltas,
                "metadata": outcome.metadata,
            },
        )
        _log_to_mlflow(outcome)


def _log_to_mlflow(outcome: RerankerExperimentOutcome) -> None:
    """Attempt to persist experiment metadata to MLflow if available."""

    if mlflow is None:  # pragma: no cover - executed only when MLflow present
        return

    manage_run = False
    try:  # pragma: no cover - MLflow integration is best-effort
        if mlflow.active_run() is None:
            mlflow.start_run(run_name="search_reranker_experiment", nested=True)
            manage_run = True
        mlflow.log_metric("ordering_changed", 1 if outcome.ordering_changed else 0)
        for identifier, delta in outcome.rank_deltas.items():
            mlflow.log_metric(f"rank_delta::{identifier}", delta)
        for identifier, delta in outcome.score_deltas.items():
            mlflow.log_metric(f"score_delta::{identifier}", delta)
        for key, value in outcome.metadata.items():
            mlflow.log_param(key, str(value))
    except Exception:
        LOGGER.debug("Failed to record reranker experiment in MLflow", exc_info=True)
    finally:  # pragma: no cover - run management is difficult to trigger deterministically
        if manage_run:
            try:
                mlflow.end_run()
            except Exception:
                LOGGER.debug("Failed to close MLflow run", exc_info=True)


_DEFAULT_SINK: ExperimentAnalyticsSink = LoggingExperimentAnalyticsSink()


def get_experiment_analytics() -> ExperimentAnalyticsSink:
    """Return the shared experiment analytics sink."""

    return _DEFAULT_SINK


def set_experiment_analytics(sink: ExperimentAnalyticsSink) -> None:
    """Override the shared experiment analytics sink (primarily for tests)."""

    global _DEFAULT_SINK
    _DEFAULT_SINK = sink


def reset_experiment_analytics() -> None:
    """Reset the shared sink to the default logging implementation."""

    set_experiment_analytics(LoggingExperimentAnalyticsSink())


__all__ = [
    "ExperimentAnalyticsSink",
    "LoggingExperimentAnalyticsSink",
    "RerankerExperimentOutcome",
    "get_experiment_analytics",
    "reset_experiment_analytics",
    "set_experiment_analytics",
    "summarise_reranker_outcome",
]

