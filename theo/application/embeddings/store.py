"""Caching layer for passage embeddings."""
from __future__ import annotations

from collections import OrderedDict
from typing import Mapping, Protocol, Sequence


class PassageEmbeddingStore(Protocol):
    """Abstract persistence layer for passage embeddings."""

    def get_embedding(self, passage_id: str) -> Sequence[float] | None:
        """Return the embedding vector for *passage_id* or ``None`` if absent."""

    def get_embeddings(
        self, passage_ids: Sequence[str]
    ) -> Mapping[str, Sequence[float] | None]:
        """Return embeddings for each id in *passage_ids*."""


class PassageEmbeddingService:
    """Caches passage embeddings fetched from an underlying store."""

    def __init__(
        self,
        store: PassageEmbeddingStore,
        *,
        cache_max_size: int | None = None,
    ) -> None:
        self._store = store
        self._cache_max_size = cache_max_size if cache_max_size and cache_max_size > 0 else None
        self._cache: OrderedDict[str, Sequence[float] | None] | None = (
            OrderedDict() if self._cache_max_size is not None else None
        )

    def get(self, passage_id: str) -> Sequence[float] | None:
        """Return the embedding vector for a passage, caching the result."""

        if not passage_id:
            return None
        if self._cache is not None and passage_id in self._cache:
            self._cache.move_to_end(passage_id)
            return self._cache[passage_id]
        embedding = self._store.get_embedding(passage_id)
        if self._cache is not None:
            self._cache[passage_id] = embedding
            self._prune_cache()
        return embedding

    def get_many(self, passage_ids: Sequence[str]) -> Mapping[str, Sequence[float] | None]:
        """Return embeddings for all *passage_ids*, using bulk fetches for misses."""

        results: dict[str, Sequence[float] | None] = {}
        missing_set: set[str] = set()  # Use set to automatically deduplicate
        
        for identifier in passage_ids:
            if not identifier:
                continue
            if self._cache is not None and identifier in self._cache:
                self._cache.move_to_end(identifier)
                results[identifier] = self._cache[identifier]
            else:
                missing_set.add(identifier)  # Automatically deduplicates
                
        if missing_set:
            # Convert back to list for backend call, preserving deduplication
            missing_list = list(missing_set)
            fetched = self._store.get_embeddings(missing_list)
            
            # Update results and cache for each missing ID
            for identifier in missing_list:
                value = fetched.get(identifier)
                results[identifier] = value
                if self._cache is not None:
                    self._cache[identifier] = value
                    
            if self._cache is not None:
                self._prune_cache()
                
        return results

    def clear_cache(self) -> None:
        """Remove all cached embeddings."""

        if self._cache is not None:
            self._cache.clear()

    def _prune_cache(self) -> None:
        if self._cache is None or self._cache_max_size is None:
            return
        while len(self._cache) > self._cache_max_size:
            self._cache.popitem(last=False)


__all__ = ["PassageEmbeddingService", "PassageEmbeddingStore"]
