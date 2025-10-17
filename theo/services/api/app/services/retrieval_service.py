"""Retrieval service orchestrating hybrid search and reranking."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Callable, Mapping, MutableMapping, Sequence

from fastapi import Depends
from sqlalchemy.orm import Session

from theo.application.facades.settings import Settings, get_settings
from ..analytics.experiments import (
    ExperimentAnalyticsSink,
    RerankerExperimentOutcome,
    get_experiment_analytics,
    summarise_reranker_outcome,
)
from ..models.search import HybridSearchRequest, HybridSearchResult
from ..ranking.mlflow_integration import is_mlflow_uri, mlflow_signature
from ..ranking.re_ranker import Reranker, load_reranker
from ..retriever.hybrid import hybrid_search
from ..telemetry import SEARCH_RERANKER_EVENTS

LOGGER = logging.getLogger(__name__)

_RERANKER_TOP_K = 20


@dataclass
class _RerankerCache:
    loader: Callable[[str, str | None], Reranker]
    lock: Lock = field(default_factory=Lock)
    reranker: Reranker | None = field(default=None, init=False)
    key: tuple[str, str | None] | None = field(default=None, init=False)
    failed: bool = field(default=False, init=False)
    cooldown_seconds: float = 60.0
    _last_failure_at: float | None = field(default=None, init=False)
    _artifact_signature: object | None = field(default=None, init=False)
    _cooldown_logged: bool = field(default=False, init=False)

    def reset(self) -> None:
        with self.lock:
            self.reranker = None
            self.key = None
            self.failed = False
            self._last_failure_at = None
            self._artifact_signature = None
            self._cooldown_logged = False

    def resolve(
        self, model_path: str | Path | None, expected_sha256: str | None
    ) -> Reranker | None:
        if model_path is None:
            return None

        model_str = str(model_path)
        cache_key = (model_str, expected_sha256)

        with self.lock:
            if self.key != cache_key:
                self.reranker = None
                self.failed = False
                self.key = cache_key
                self._last_failure_at = None
                self._artifact_signature = None
                self._cooldown_logged = False

            signature = self._snapshot_artifact(model_str)

            if self.failed:
                if signature != self._artifact_signature:
                    self.failed = False
                    self.reranker = None
                    self._last_failure_at = None
                    self._cooldown_logged = False
                else:
                    if self._last_failure_at is not None:
                        elapsed = time.monotonic() - self._last_failure_at
                        if elapsed < self.cooldown_seconds:
                            remaining = self.cooldown_seconds - elapsed
                            if not self._cooldown_logged:
                                retry_at = datetime.now(timezone.utc) + timedelta(
                                    seconds=remaining
                                )
                                LOGGER.info(
                                    "search.reranker_retry_pending",
                                    extra={
                                        "event": "search.reranker_retry_pending",
                                        "model_path": model_str,
                                        "retry_in_seconds": round(remaining, 3),
                                        "retry_at": retry_at.isoformat(),
                                    },
                                )
                                self._cooldown_logged = True
                            return None
                    self.failed = False
                    self.reranker = None
                    self._last_failure_at = None
                    self._cooldown_logged = False

            if self.reranker is None:
                try:
                    self.reranker = self.loader(
                        model_str, expected_sha256=expected_sha256
                    )
                    self._artifact_signature = signature
                    self._last_failure_at = None
                    self._cooldown_logged = False
                except Exception as exc:  # pragma: no cover - defensive logging handled upstream
                    previously_failed = self.failed
                    self.failed = True
                    self._last_failure_at = time.monotonic()
                    self._artifact_signature = signature
                    self._cooldown_logged = False
                    if not previously_failed:
                        LOGGER.exception(
                            "search.reranker_load_failed",
                            extra={
                                "event": "search.reranker_load_failed",
                                "model_path": model_str,
                                "error": str(exc),
                            },
                        )
                        SEARCH_RERANKER_EVENTS.labels(event="load_failed").inc()
                    retry_in = self.cooldown_seconds
                    retry_at = datetime.now(timezone.utc) + timedelta(
                        seconds=retry_in
                    )
                    LOGGER.info(
                        "search.reranker_retry_scheduled",
                        extra={
                            "event": "search.reranker_retry_scheduled",
                            "model_path": model_str,
                            "retry_in_seconds": retry_in,
                            "retry_at": retry_at.isoformat(),
                        },
                    )
                    return None

            return self.reranker

    @staticmethod
    def _snapshot_artifact(path: str) -> object | None:
        if is_mlflow_uri(path):
            return mlflow_signature(path)
        try:
            stat = Path(path).stat()
        except OSError:
            return None
        return int(stat.st_mtime_ns), stat.st_size


_DEFAULT_RERANKER_CACHE = _RerankerCache(load_reranker)


def _configure_mlflow_clients(settings: Settings) -> None:
    try:  # pragma: no cover - exercised in environments without MLflow
        import mlflow
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        return

    if settings.mlflow_tracking_uri:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    if settings.mlflow_registry_uri:
        mlflow.set_registry_uri(settings.mlflow_registry_uri)


def _iter_reranker_references(
    settings: Settings,
) -> list[tuple[str | Path, str | None]]:
    references: list[tuple[str | Path, str | None]] = []
    registry_uri = getattr(settings, "reranker_model_registry_uri", None)
    if registry_uri:
        references.append((registry_uri, None))
    model_path = getattr(settings, "reranker_model_path", None)
    if model_path:
        references.append((model_path, getattr(settings, "reranker_model_sha256", None)))
    return references


def _format_reranker_header(reference: str | Path | None) -> str | None:
    if reference is None:
        return None
    if is_mlflow_uri(reference):
        text = str(reference).rstrip("/")
        if "@" in text:
            alias = text.split("@", 1)[1]
            return alias.split("/", 1)[0]
        segments = [segment for segment in text.split("/") if segment]
        if segments:
            return segments[-1]
        return text
    ref_path = Path(reference)
    return ref_path.name or str(ref_path)


@dataclass
class RetrievalService:
    """Coordinate hybrid retrieval and optional reranking."""

    settings: Settings
    search_fn: Callable[[Session, HybridSearchRequest], Sequence[HybridSearchResult]]
    reranker_cache: _RerankerCache = field(default_factory=lambda: _RerankerCache(load_reranker))
    reranker_top_k: int = _RERANKER_TOP_K
    experiment_analytics: ExperimentAnalyticsSink | None = None
    experimental_reranker_loaders: MutableMapping[
        str, Callable[[Settings, Mapping[str, str]], tuple[Reranker | None, str | None]]
    ] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.experiment_analytics is None:
            self.experiment_analytics = get_experiment_analytics()

    def search(
        self,
        session: Session,
        request: HybridSearchRequest,
        experiments: Mapping[str, str] | None = None,
    ) -> tuple[list[HybridSearchResult], str | None]:
        """Execute hybrid search and return results with optional reranker header."""

        results = [item for item in self.search_fn(session, request)]
        baseline = [item.model_copy(deep=True) for item in results]
        reranker_header: str | None = None
        experiments = dict(experiments or {})
        strategy = self._resolve_reranker_strategy(experiments)
        rerank_applied = False

        reranker: Reranker | None = None
        model_path: Path | None = None
        top_n = min(len(results), self.reranker_top_k)
        reranker_requested = strategy not in {"none", "bm25", "off", "disabled"}
        has_reranker_experiment = "reranker" in experiments
        experiment_overrides_default = has_reranker_experiment and strategy != "default"
        should_attempt_rerank = reranker_requested and (
            self._should_rerank() or experiment_overrides_default
        )

        if top_n and should_attempt_rerank:
            reranker, reranker_header = self._load_reranker_for_strategy(strategy, experiments)
            if strategy == "default" and self.settings.reranker_model_path is not None:
                model_path = Path(self.settings.reranker_model_path)
            if reranker is not None and reranker_header is None:
                if self.settings.reranker_model_path is not None:
                    model_path = Path(self.settings.reranker_model_path)
                    reranker_header = model_path.name or str(model_path)
            elif reranker is None and strategy not in {"default"}:
                # Strategy requested a reranker but none could be loaded.
                LOGGER.debug(
                    "search.reranker_strategy_unavailable",
                    extra={
                        "event": "search.reranker_strategy_unavailable",
                        "strategy": strategy,
                        "experiments": experiments,
                    },
                )
        elif strategy in {"none", "bm25", "off", "disabled"}:
            LOGGER.debug(
                "search.reranker_strategy_skipped",
                extra={
                    "event": "search.reranker_strategy_skipped",
                    "strategy": strategy,
                    "experiments": experiments,
                },
            )

        if reranker is not None and top_n:
            try:
                reranked_head = reranker.rerank(results[:top_n])
                ordered = list(reranked_head) + results[top_n:]
                for index, item in enumerate(ordered, start=1):
                    item.rank = index
                results = ordered
                rerank_applied = True
            except Exception as exc:
                path_str = str(model_path) if model_path is not None else "<unknown>"
                LOGGER.exception(
                    "search.reranker_execution_failed",
                    extra={
                        "event": "search.reranker_execution_failed",
                        "model_path": path_str,
                        "strategy": strategy,
                        "error": str(exc),
                    },
                )
                SEARCH_RERANKER_EVENTS.labels(event="execution_failed").inc()

        self._record_experiments(
            experiments=experiments,
            baseline=baseline,
            variant=[item.model_copy(deep=True) for item in results],
            strategy=strategy,
            rerank_applied=rerank_applied,
            reranker_header=reranker_header,
        )
        if self._should_rerank():
            _configure_mlflow_clients(self.settings)
            reranker: Reranker | None = None
            header_reference: str | Path | None = None
            references = _iter_reranker_references(self.settings)

            cached_key = self.reranker_cache.key
            if (
                cached_key
                and self.reranker_cache.reranker is not None
                and not self.reranker_cache.failed
            ):
                cached_path, cached_digest = cached_key
                for index, (reference, digest) in enumerate(references):
                    if str(reference) == cached_path and digest == cached_digest:
                        if index != 0:
                            references = [
                                references[index],
                                *references[:index],
                                *references[index + 1 :],
                            ]
                        break

            for reference, digest in references:
                reranker = self.reranker_cache.resolve(reference, digest)
                if reranker is not None:
                    header_reference = reference
                    break
            else:
                header_reference = None
            if reranker is not None:
                try:
                    top_n = min(len(results), self.reranker_top_k)
                    if top_n:
                        reranked_head = reranker.rerank(results[:top_n])
                        ordered = list(reranked_head) + results[top_n:]
                        for index, item in enumerate(ordered, start=1):
                            item.rank = index
                        results = ordered
                        reranker_header = _format_reranker_header(header_reference)
                except Exception as exc:
                    path_str = _format_reranker_header(header_reference) or "<unknown>"
                    LOGGER.exception(
                        "search.reranker_execution_failed",
                        extra={
                            "event": "search.reranker_execution_failed",
                            "model_path": path_str,
                            "error": str(exc),
                        },
                    )
                    SEARCH_RERANKER_EVENTS.labels(event="execution_failed").inc()

        return results, reranker_header

    def _should_rerank(self) -> bool:
        if not getattr(self.settings, "reranker_enabled", False):
            return False
        return bool(
            getattr(self.settings, "reranker_model_registry_uri", None)
            or getattr(self.settings, "reranker_model_path", None)
        )

    def _resolve_reranker_strategy(self, experiments: Mapping[str, str]) -> str:
        strategy = experiments.get("reranker")
        if not strategy:
            return "default"
        normalized = strategy.strip().casefold()
        if normalized in {"control", "baseline", "default"}:
            return "default"
        return normalized

    def _load_reranker_for_strategy(
        self, strategy: str, experiments: Mapping[str, str]
    ) -> tuple[Reranker | None, str | None]:
        if strategy in {"none", "bm25", "off", "disabled"}:
            return None, None

        if strategy == "default":
            reranker = self.reranker_cache.resolve(
                self.settings.reranker_model_path,
                self.settings.reranker_model_sha256,
            )
            if reranker is None:
                return None, None
            header: str | None = None
            if self.settings.reranker_model_path is not None:
                model_path = Path(self.settings.reranker_model_path)
                header = model_path.name or str(model_path)
            return reranker, header

        loader = self.experimental_reranker_loaders.get(strategy)
        if loader is None:
            LOGGER.debug(
                "search.reranker_strategy_unknown",
                extra={
                    "event": "search.reranker_strategy_unknown",
                    "strategy": strategy,
                    "experiments": experiments,
                },
            )
            return self._load_reranker_for_strategy("default", experiments)

        try:
            return loader(self.settings, experiments)
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.exception(
                "search.reranker_strategy_failed",
                extra={
                    "event": "search.reranker_strategy_failed",
                    "strategy": strategy,
                    "error": str(exc),
                },
            )
            return None, None

    def _record_experiments(
        self,
        *,
        experiments: Mapping[str, str],
        baseline: Sequence[HybridSearchResult],
        variant: Sequence[HybridSearchResult],
        strategy: str,
        rerank_applied: bool,
        reranker_header: str | None,
    ) -> None:
        if not experiments or "reranker" not in experiments:
            return
        if self.experiment_analytics is None:
            return

        metadata: dict[str, object] = {
            "applied": rerank_applied,
            "strategy": strategy,
            "reranker_header": reranker_header,
            "reranker_enabled": self._should_rerank(),
        }

        for key, value in experiments.items():
            if key == "reranker":
                continue
            metadata[f"experiment_{key}"] = value

        outcome: RerankerExperimentOutcome = summarise_reranker_outcome(
            experiment=experiments["reranker"],
            strategy=strategy,
            baseline=baseline,
            variant=variant,
            metadata=metadata,
        )
        try:
            self.experiment_analytics.record_reranker_outcome(outcome)
        except Exception:  # pragma: no cover - diagnostics only
            LOGGER.exception(
                "search.reranker_experiment_record_failed",
                extra={
                    "event": "search.reranker_experiment_record_failed",
                    "strategy": strategy,
                    "experiments": experiments,
                },
            )


def get_retrieval_service(
    settings: Settings = Depends(get_settings),
) -> RetrievalService:
    """Dependency factory for :class:`RetrievalService`."""

    return RetrievalService(
        settings=settings,
        search_fn=hybrid_search,
        reranker_cache=_DEFAULT_RERANKER_CACHE,
    )


def reset_reranker_cache() -> None:
    """Reset the shared reranker cache used by the default dependency."""

    _DEFAULT_RERANKER_CACHE.reset()
