"""Redis caching helpers for guardrailed RAG workflows."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Callable

from ...core.settings import get_settings
from ...core.version import get_git_sha

if TYPE_CHECKING:
    from .workflow import RAGAnswer
else:  # pragma: no cover - used only for type checking
    RAGAnswer = Any  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency guard
    import redis
except ImportError:  # pragma: no cover - redis is optional at runtime
    redis = None  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)
_CACHE_TTL_SECONDS = 30 * 60


def _normalise_segment(value: str | None, default: str) -> str:
    segment = value or default
    return re.sub(r"[^a-zA-Z0-9._-]", "_", segment)


@dataclass(slots=True)
class CacheLookupResult:
    status: str
    payload: dict[str, Any] | None = None
    cache_key: str | None = None


class RAGCache:
    """Thin wrapper around Redis for caching guardrailed answers."""

    def __init__(self, *, redis_module: Any | None = None) -> None:
        self._redis_module = redis_module if redis_module is not None else redis
        self._client: Any | None = None

    # Redis initialisation -------------------------------------------------
    def _initialise_client(self) -> Any | None:
        if self._redis_module is None:  # pragma: no cover - optional dependency
            return None
        if self._client is not None:
            return self._client
        try:
            settings = get_settings()
            self._client = self._redis_module.Redis.from_url(  # type: ignore[assignment]
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        except Exception:  # pragma: no cover - network/config errors
            LOGGER.debug("failed to initialise redis client", exc_info=True)
            self._client = None
        return self._client

    def _execute(self, callback: Callable[[Any], Any]) -> Any | None:
        client = self._initialise_client()
        if client is None:
            return None
        try:
            return callback(client)
        except Exception:  # pragma: no cover - redis failures logged at debug
            LOGGER.debug("redis command failed", exc_info=True)
            return None

    # Key helpers ---------------------------------------------------------
    def build_key(
        self,
        *,
        user_id: str | None,
        model_label: str | None,
        prompt: str,
        retrieval_digest: str,
    ) -> str:
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        version = _normalise_segment(get_git_sha() or "dev", "dev")
        user_segment = _normalise_segment(user_id, "anon")
        model_segment = _normalise_segment(model_label, "default")
        return f"rag:{version}:{user_segment}:{model_segment}:{retrieval_digest}:{prompt_hash}"

    # Persistence ---------------------------------------------------------
    def load(self, key: str) -> dict[str, Any] | None:
        raw = self._execute(lambda client: client.get(key))
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            LOGGER.debug("invalid JSON payload in cache for key %s", key, exc_info=True)
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def store(
        self,
        key: str,
        *,
        answer: "RAGAnswer",
        validation: dict[str, Any] | None,
    ) -> None:
        payload = {
            "answer": answer.model_dump(mode="json"),
            "validation": validation,
            "model_name": answer.model_name,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        try:
            serialised = json.dumps(payload)
        except TypeError:
            LOGGER.debug("failed to serialise cache payload", exc_info=True)
            return
        self._execute(lambda client: client.set(key, serialised, ex=_CACHE_TTL_SECONDS))

    def delete(self, key: str) -> None:
        self._execute(lambda client: client.delete(key))

    # Convenience ---------------------------------------------------------
    def lookup(
        self,
        *,
        user_id: str | None,
        model_label: str | None,
        prompt: str,
        retrieval_digest: str,
    ) -> CacheLookupResult:
        key = self.build_key(
            user_id=user_id,
            model_label=model_label,
            prompt=prompt,
            retrieval_digest=retrieval_digest,
        )
        payload = self.load(key)
        status = "hit" if payload else "miss"
        return CacheLookupResult(status=status, payload=payload, cache_key=key)


__all__ = ["CacheLookupResult", "RAGCache"]
