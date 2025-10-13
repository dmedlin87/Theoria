"""Retrieval service orchestrating hybrid search and reranking."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Callable, Sequence

from fastapi import Depends
from sqlalchemy.orm import Session

from theo.application.facades.settings import Settings, get_settings
from ..models.search import HybridSearchRequest, HybridSearchResult
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
    _artifact_signature: tuple[int, int] | None = field(default=None, init=False)
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
    def _snapshot_artifact(path: str) -> tuple[int, int] | None:
        try:
            stat = Path(path).stat()
        except OSError:
            return None
        return int(stat.st_mtime_ns), stat.st_size


_DEFAULT_RERANKER_CACHE = _RerankerCache(load_reranker)


@dataclass
class RetrievalService:
    """Coordinate hybrid retrieval and optional reranking."""

    settings: Settings
    search_fn: Callable[[Session, HybridSearchRequest], Sequence[HybridSearchResult]]
    reranker_cache: _RerankerCache = field(default_factory=lambda: _RerankerCache(load_reranker))
    reranker_top_k: int = _RERANKER_TOP_K

    def search(
        self, session: Session, request: HybridSearchRequest
    ) -> tuple[list[HybridSearchResult], str | None]:
        """Execute hybrid search and return results with optional reranker header."""

        results = [item for item in self.search_fn(session, request)]
        reranker_header: str | None = None

        if self._should_rerank():
            reranker = self.reranker_cache.resolve(
                self.settings.reranker_model_path,
                self.settings.reranker_model_sha256,
            )
            if reranker is not None:
                model_path = (
                    Path(self.settings.reranker_model_path)
                    if self.settings.reranker_model_path is not None
                    else None
                )
                try:
                    top_n = min(len(results), self.reranker_top_k)
                    if top_n:
                        reranked_head = reranker.rerank(results[:top_n])
                        ordered = list(reranked_head) + results[top_n:]
                        for index, item in enumerate(ordered, start=1):
                            item.rank = index
                        results = ordered
                        if model_path is not None:
                            reranker_header = model_path.name or str(model_path)
                except Exception as exc:
                    path_str = str(model_path) if model_path is not None else "<unknown>"
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
        return bool(
            getattr(self.settings, "reranker_enabled", False)
            and getattr(self.settings, "reranker_model_path", None)
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
