"""In-memory cache utilities for AI responses."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class CacheManager:
    """Simple async-friendly cache manager with TTL support."""

    def __init__(self, default_ttl: timedelta = timedelta(hours=1)) -> None:
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Return a cached value if it has not expired."""

        entry = self._cache.get(key)
        if not entry:
            return None
        if datetime.utcnow() >= entry["expires_at"]:
            self._cache.pop(key, None)
            return None
        return entry["value"]

    async def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """Store a value in the cache with an optional TTL override."""

        expires_at = datetime.utcnow() + (ttl or self.default_ttl)
        self._cache[key] = {
            "value": value,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
        }

    async def clear(self, older_than: Optional[timedelta] = None) -> None:
        """Clear cache entries, optionally only those older than ``older_than``."""

        if older_than is None:
            self._cache.clear()
            return

        threshold = datetime.utcnow() - older_than
        expired_keys = [
            key
            for key, entry in self._cache.items()
            if entry["created_at"] <= threshold
        ]
        for key in expired_keys:
            self._cache.pop(key, None)


__all__ = ["CacheManager"]
