"""Utilities for generating dense embeddings during ingestion."""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import threading
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from typing import Protocol, cast

from opentelemetry import trace
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ClauseElement

try:  # pragma: no cover - heavy dependency may be unavailable in tests
    from FlagEmbedding import FlagModel as _RuntimeFlagModel
except Exception:  # pragma: no cover - optional dependency
    _RuntimeFlagModel = None


class _EmbeddingBackend(Protocol):
    """Protocol representing the minimal surface of the embedding backend."""

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        ...

from theo.application.facades.settings import get_settings

from theo.application.facades.resilience import ResilienceError, ResilienceSettings, resilient_operation
from theo.application.facades.telemetry import set_span_attribute

_LOGGER = logging.getLogger(__name__)
_TRACER = trace.get_tracer("theo.embedding")


def _flag_model_enabled() -> bool:
    """Return True when the runtime embedding model should be used."""

    if _RuntimeFlagModel is None:
        return False
    if os.environ.get("THEO_FORCE_EMBEDDING_FALLBACK"):
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True


def _normalise(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return [0.0 for _ in vector]
    return [float(component) / norm for component in vector]


class _FallbackEmbedder:
    """Deterministic embedding generator used when the real model is unavailable."""

    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            values: list[float] = []
            while len(values) < self.dimension:
                for index in range(0, len(digest), 4):
                    chunk = digest[index : index + 4]
                    if len(chunk) < 4:
                        chunk = chunk.ljust(4, b"\0")
                    integer = int.from_bytes(chunk, "little", signed=False)
                    values.append((integer % 1000) / 1000.0)
                    if len(values) >= self.dimension:
                        break
                digest = hashlib.sha256(digest).digest()
            embeddings.append(_normalise(values[: self.dimension]))
        return embeddings


class EmbeddingService:
    """Lazily-loaded embedding backend supporting batching and normalisation."""

    def __init__(
        self,
        model_name: str,
        dimension: int,
        *,
        cache_max_size: int | None = 1024,
    ) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self._model: _EmbeddingBackend | None = None
        self._lock = threading.Lock()
        if cache_max_size is not None and cache_max_size < 0:
            raise ValueError("cache_max_size must be non-negative or None")
        self._cache_max_size = cache_max_size
        self._cache: "OrderedDict[str, tuple[float, ...]]" = OrderedDict()

    def _ensure_model(self) -> _EmbeddingBackend:
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                if _flag_model_enabled():
                    try:
                        self._model = _RuntimeFlagModel(  # type: ignore[call-arg]
                            self.model_name,
                            use_fp16=False,
                        )
                    except Exception:  # pragma: no cover - defensive fallback
                        _LOGGER.warning(
                            "Falling back to deterministic embeddings after "
                            "FlagModel initialisation failure",
                            exc_info=True,
                        )
                        self._model = _FallbackEmbedder(self.dimension)
                if self._model is None:
                    self._model = _FallbackEmbedder(self.dimension)
        assert self._model is not None
        return self._model

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._ensure_model()
        raw_embeddings: object
        if hasattr(model, "encode"):
            try:
                embeddings, metadata = resilient_operation(
                    lambda: model.encode(texts),
                    key=f"embedding:{self.model_name}",
                    classification="embedding",
                    settings=ResilienceSettings(max_attempts=2),
                )
                span = trace.get_current_span()
                if span is not None:
                    span.set_attribute("embedding.resilience_attempts", metadata.attempts)
                    span.set_attribute("embedding.resilience_duration", metadata.duration)
                raw_embeddings = embeddings
            except ResilienceError:
                raise
        else:  # pragma: no cover - extremely defensive
            raw_embeddings = []

        if isinstance(raw_embeddings, Sequence):
            if len(raw_embeddings) > 0 and isinstance(raw_embeddings[0], Sequence):
                vectors_iterable: Iterable[Iterable[float]] = cast(
                    Sequence[Sequence[float]], raw_embeddings
                )
            else:
                vectors_iterable = cast(Iterable[Iterable[float]], raw_embeddings)
        else:
            vectors_iterable = cast(Iterable[Iterable[float]], raw_embeddings)

        raw_vectors = [
            [float(component) for component in vector]
            for vector in vectors_iterable
        ]
        return [_normalise(vector) for vector in raw_vectors]

    def embed(self, texts: Sequence[str], *, batch_size: int = 32) -> list[list[float]]:
        batched: list[list[float]] = []
        if not texts:
            return batched
        for batch_index, start in enumerate(range(0, len(texts), batch_size)):
            batch = texts[start : start + batch_size]
            with _TRACER.start_as_current_span("embedding.batch") as span:
                span.set_attribute("embedding.model_name", self.model_name)
                span.set_attribute("embedding.batch_index", batch_index)
                span.set_attribute("embedding.batch_size", len(batch))
                span.set_attribute("embedding.vector_dimensions", self.dimension)
                cached_vectors: list[list[float] | None] = [None] * len(batch)
                miss_requests: list[tuple[int, str]] = []
                unique_misses: list[str] = []
                seen_misses: set[str] = set()
                with self._lock:
                    for index, text in enumerate(batch):
                        cached = self._cache.get(text)
                        if cached is not None:
                            self._cache.move_to_end(text)
                            cached_vectors[index] = list(cached)
                        else:
                            miss_requests.append((index, text))
                            if text not in seen_misses:
                                seen_misses.add(text)
                                unique_misses.append(text)
                span.set_attribute("embedding.cache_miss_count", len(unique_misses))
                span.set_attribute("embedding.cache_hit_count", len(batch) - len(miss_requests))
                new_vectors: dict[str, list[float]] = {}
                try:
                    if unique_misses:
                        encoded = self._encode(unique_misses)
                        new_vectors = {
                            text: list(vector)
                            for text, vector in zip(unique_misses, encoded)
                        }
                except ResilienceError as exc:
                    span.set_attribute("embedding.resilience_category", exc.metadata.category)
                    span.set_attribute("embedding.resilience_attempts", exc.metadata.attempts)
                    raise
                if unique_misses and len(new_vectors) != len(unique_misses):  # pragma: no cover
                    raise RuntimeError("Embedding backend returned unexpected vector count")
                if new_vectors:
                    for index, text in miss_requests:
                        cached_vectors[index] = list(new_vectors[text])
                    if self._cache_max_size is None or self._cache_max_size > 0:
                        with self._lock:
                            for text, vector in new_vectors.items():
                                self._cache[text] = tuple(vector)
                                self._cache.move_to_end(text)
                                if self._cache_max_size is not None:
                                    while len(self._cache) > self._cache_max_size:
                                        self._cache.popitem(last=False)
                for index, _text in miss_requests:
                    if cached_vectors[index] is None:  # pragma: no cover - defensive
                        raise RuntimeError("Missing embedding vector for cache miss")
                vectors = [
                    cached_vectors[index]
                    if cached_vectors[index] is not None
                    else [0.0] * self.dimension
                    for index in range(len(batch))
                ]
                span.set_attribute("embedding.output_count", len(vectors))
            batched.extend(vectors)
        return batched

    def clear_cache(self) -> None:
        """Clear any cached embedding vectors."""

        with self._lock:
            self._cache.clear()


_service: EmbeddingService | None = None
_NON_ALNUM_RE = re.compile(r"[^0-9a-zA-Z]+")


def get_embedding_service() -> EmbeddingService:
    """Return a process-wide embedding service instance."""

    global _service
    if _service is None:
        settings = get_settings()
        _service = EmbeddingService(
            settings.embedding_model,
            settings.embedding_dim,
            cache_max_size=settings.embedding_cache_size,
        )
    return _service


def clear_embedding_cache() -> None:
    """Clear cached embeddings held by the shared service instance."""

    global _service
    if _service is not None:
        _service.clear_cache()


def lexical_representation(session: Session, text: str) -> ClauseElement | str:
    """Return a stored representation for lexical indexing.

    When a PostgreSQL connection is available a ``to_tsvector`` expression is
    returned so that the server generates the tsvector directly. For other
    dialects (e.g., SQLite during tests) a simplified lower-cased token stream
    is used instead.
    """

    bind = getattr(session, "bind", None)
    dialect_name = (
        getattr(bind.dialect, "name", "sqlite") if bind is not None else "sqlite"
    )
    if dialect_name == "postgresql":
        from sqlalchemy import func

        return func.to_tsvector("english", text)
    normalised = _NON_ALNUM_RE.sub(" ", text.lower())
    tokens = [token for token in normalised.split() if token]
    return " ".join(tokens)
