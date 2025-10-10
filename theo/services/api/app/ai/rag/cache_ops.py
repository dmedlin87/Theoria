"""Cache helpers for RAG workflows."""

from __future__ import annotations

from typing import Any

from .cache import RAGCache
from .models import RAGAnswer


DEFAULT_CACHE = RAGCache()


def build_cache_key(
    *,
    user_id: str | None,
    model_label: str | None,
    prompt: str,
    retrieval_digest: str,
    cache: RAGCache = DEFAULT_CACHE,
) -> str:
    """Construct a cache key for the provided context."""

    return cache.build_key(
        user_id=user_id,
        model_label=model_label,
        prompt=prompt,
        retrieval_digest=retrieval_digest,
    )


def load_cached_answer(key: str, *, cache: RAGCache = DEFAULT_CACHE) -> dict[str, Any] | None:
    """Load a cached answer payload if present."""

    return cache.load(key)


def store_cached_answer(
    key: str,
    *,
    answer: RAGAnswer,
    validation: dict[str, Any] | None,
    cache: RAGCache = DEFAULT_CACHE,
) -> None:
    """Persist an answer and its validation metadata to the cache."""

    cache.store(key, answer=answer, validation=validation)


__all__ = [
    "DEFAULT_CACHE",
    "RAGCache",
    "build_cache_key",
    "load_cached_answer",
    "store_cached_answer",
]
