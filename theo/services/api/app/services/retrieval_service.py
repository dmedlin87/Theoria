"""Retrieval service orchestrating hybrid search and reranking."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Callable, Sequence

from fastapi import Depends
from sqlalchemy.orm import Session

from ..core.settings import Settings, get_settings
from ..models.search import HybridSearchRequest, HybridSearchResult
from ..ranking.re_ranker import Reranker, load_reranker
from ..retriever.hybrid import hybrid_search

LOGGER = logging.getLogger(__name__)

_RERANKER_TOP_K = 20


@dataclass
class _RerankerCache:
    loader: Callable[[str, str | None], Reranker]
    lock: Lock = field(default_factory=Lock)
    reranker: Reranker | None = field(default=None, init=False)
    key: tuple[str, str | None] | None = field(default=None, init=False)
    failed: bool = field(default=False, init=False)

    def reset(self) -> None:
        with self.lock:
            self.reranker = None
            self.key = None
            self.failed = False

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

            if self.failed:
                return None

            if self.reranker is None:
                try:
                    self.reranker = self.loader(
                        model_str, expected_sha256=expected_sha256
                    )
                except Exception as exc:  # pragma: no cover - defensive logging handled upstream
                    should_log = not self.failed
                    self.failed = True
                    if should_log:
                        LOGGER.exception(
                            "search.reranker_load_failed",
                            extra={
                                "event": "search.reranker_load_failed",
                                "model_path": model_str,
                                "error": str(exc),
                            },
                        )
                    return None

            return self.reranker


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
                try:
                    top_n = min(len(results), self.reranker_top_k)
                    if top_n:
                        reranked_head = reranker.rerank(results[:top_n])
                        ordered = list(reranked_head) + results[top_n:]
                        for index, item in enumerate(ordered, start=1):
                            item.rank = index
                        results = ordered
                        model_path = Path(self.settings.reranker_model_path)
                        reranker_header = model_path.name or str(model_path)
                except Exception:
                    pass

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
