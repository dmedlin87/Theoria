"""Utilities for generating dense embeddings during ingestion."""

from __future__ import annotations

import hashlib
import math
import threading
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

from ..core.settings import get_settings
from ..resilience import ResilienceError, ResiliencePolicy, resilient_operation


_TRACER = trace.get_tracer("theo.embedding")


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

    def __init__(self, model_name: str, dimension: int) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self._model: _EmbeddingBackend | None = None
        self._lock = threading.Lock()

    def _ensure_model(self) -> _EmbeddingBackend:
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                if _RuntimeFlagModel is not None:
                    self._model = _RuntimeFlagModel(self.model_name, use_fp16=False)
                else:
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
                    policy=ResiliencePolicy(max_attempts=2),
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
                try:
                    vectors = self._encode(batch)
                except ResilienceError as exc:
                    span.set_attribute("embedding.resilience_category", exc.metadata.category)
                    span.set_attribute("embedding.resilience_attempts", exc.metadata.attempts)
                    raise
                span.set_attribute("embedding.output_count", len(vectors))
            batched.extend(vectors)
        return batched


_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Return a process-wide embedding service instance."""

    global _service
    if _service is None:
        settings = get_settings()
        _service = EmbeddingService(settings.embedding_model, settings.embedding_dim)
    return _service


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
    tokens = [token for token in text.lower().split() if token]
    return " ".join(tokens)
