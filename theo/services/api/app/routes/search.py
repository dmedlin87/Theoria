"""Search endpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Callable

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.settings import get_settings
from ..models.search import (
    HybridSearchFilters,
    HybridSearchRequest,
    HybridSearchResponse,
)
from ..retriever.hybrid import hybrid_search
from ..ranking.re_ranker import Reranker, load_reranker

router = APIRouter()


_RERANKER_TOP_K = 20


LOGGER = logging.getLogger(__name__)


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
                except Exception as exc:  # pragma: no cover - logged for observability
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


_RERANKER_CACHE = _RerankerCache(load_reranker)


def _reset_reranker_cache() -> None:
    _RERANKER_CACHE.reset()


def reset_reranker_cache() -> None:
    """Expose a reset hook for tests."""

    _reset_reranker_cache()


def _resolve_reranker(
    model_path: str | Path | None, expected_sha256: str | None
) -> Reranker | None:

    return _RERANKER_CACHE.resolve(model_path, expected_sha256)


@router.get("/", response_model=HybridSearchResponse)
def search(
    response: Response,
    q: str | None = Query(default=None, description="Keyword query"),
    osis: str | None = Query(default=None, description="Normalized OSIS reference"),
    collection: str | None = Query(
        default=None, description="Restrict to a collection"
    ),
    author: str | None = Query(default=None, description="Filter by author"),
    source_type: str | None = Query(
        default=None, description="Restrict to a source type"
    ),
    theological_tradition: str | None = Query(
        default=None,
        description="Restrict to documents aligned with a theological tradition",
    ),
    topic_domain: str | None = Query(
        default=None,
        description="Restrict to documents tagged with a topic domain",
    ),
    k: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> HybridSearchResponse:
    """Perform hybrid search over the indexed corpus."""

    request = HybridSearchRequest(
        query=q,
        osis=osis,
        filters=HybridSearchFilters(
            collection=collection,
            author=author,
            source_type=source_type,
            theological_tradition=theological_tradition,
            topic_domain=topic_domain,
        ),
        k=k,
    )
    results = hybrid_search(session, request)

    settings = get_settings()
    if settings.reranker_enabled and settings.reranker_model_path:
        reranker = _resolve_reranker(
            settings.reranker_model_path, settings.reranker_model_sha256
        )
        if reranker is not None:
            try:
                top_n = min(len(results), _RERANKER_TOP_K)
                if top_n:
                    reranked_head = reranker.rerank(results[:top_n])
                    ordered = reranked_head + results[top_n:]
                    for index, item in enumerate(ordered, start=1):
                        item.rank = index
                    response.headers["X-Reranker"] = (
                        Path(settings.reranker_model_path).name
                        or str(settings.reranker_model_path)
                    )
                    results = ordered
            except Exception:
                pass

    return HybridSearchResponse(query=q, osis=osis, results=results)
