"""Application service orchestrating embedding rebuild workflows."""

from __future__ import annotations

import itertools
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Protocol

from sqlalchemy.exc import SQLAlchemyError

from theo.application.interfaces import SessionProtocol
from theo.application.repositories.embedding_repository import (
    EmbeddingUpdate,
    Metadata,
    PassageEmbeddingRepository,
    PassageForEmbedding,
)


class EmbeddingBackendProtocol(Protocol):
    """Minimal surface exposed by embedding service implementations."""

    def embed(
        self, texts: Sequence[str], *, batch_size: int
    ) -> Sequence[Sequence[float]]: ...


@dataclass(frozen=True)
class EmbeddingRebuildState:
    """Represents the persisted progress of an embedding rebuild."""

    processed: int
    total: int
    last_id: str | None
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class EmbeddingRebuildProgress:
    """Information emitted after processing an embedding batch."""

    batch_index: int
    batch_size: int
    batch_duration: float
    rate_per_passage: float
    state: EmbeddingRebuildState


@dataclass(frozen=True)
class EmbeddingRebuildStart:
    """Initial metadata describing the rebuild plan."""

    total: int
    missing_ids: list[str]
    skip_count: int


@dataclass(frozen=True)
class EmbeddingRebuildResult:
    """Summary of the embedding rebuild operation."""

    processed: int
    total: int
    duration: float
    missing_ids: list[str]
    metadata: Mapping[str, object]


@dataclass(slots=True)
class EmbeddingRebuildOptions:
    """Inputs configuring an embedding rebuild run."""

    fast: bool
    batch_size: int
    changed_since: datetime | None = None
    ids: Sequence[str] | None = None
    skip_count: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)
    clear_cache: bool = False


class EmbeddingRebuildError(RuntimeError):
    """Raised when embedding rebuild operations fail."""


class EmbeddingRebuildService:
    """Coordinates persistence and embedding adapters for rebuild workflows."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], SessionProtocol],
        repository_factory: Callable[[SessionProtocol], PassageEmbeddingRepository],
        embedding_service: EmbeddingBackendProtocol,
        sanitize_text: Callable[[str], str],
        cache_clearer: Callable[[], None] | None = None,
        commit_attempts: int = 3,
        commit_backoff: float = 0.5,
    ) -> None:
        if commit_attempts <= 0:
            raise ValueError("commit_attempts must be positive")
        if commit_backoff < 0:
            raise ValueError("commit_backoff cannot be negative")
        self._session_factory = session_factory
        self._repository_factory = repository_factory
        self._embedding_service = embedding_service
        self._sanitize_text = sanitize_text
        self._cache_clearer = cache_clearer
        self._commit_attempts = commit_attempts
        self._commit_backoff = commit_backoff

    def rebuild_embeddings(
        self,
        options: EmbeddingRebuildOptions,
        *,
        on_start: Callable[[EmbeddingRebuildStart], None] | None = None,
        on_progress: Callable[[EmbeddingRebuildProgress], None] | None = None,
        checkpoint: Callable[[EmbeddingRebuildState], None] | None = None,
    ) -> EmbeddingRebuildResult:
        """Execute the embedding rebuild flow using provided options."""

        if options.batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")

        start_time = time.perf_counter()
        metadata = dict(options.metadata)

        if options.clear_cache and self._cache_clearer is not None:
            self._cache_clearer()

        session = self._session_factory()
        try:
            repository = self._repository_factory(session)

            ids = list(dict.fromkeys(options.ids or []))
            missing_ids: list[str] = []
            if ids:
                existing = repository.existing_ids(ids)
                missing_ids = [identifier for identifier in ids if identifier not in existing]

            total = repository.count_candidates(
                fast=options.fast,
                changed_since=options.changed_since,
                ids=ids or None,
            )
            skip_count = min(max(options.skip_count, 0), total)

            if on_start is not None:
                on_start(
                    EmbeddingRebuildStart(
                        total=total,
                        missing_ids=missing_ids,
                        skip_count=skip_count,
                    )
                )

            if total == 0:
                duration = time.perf_counter() - start_time
                return EmbeddingRebuildResult(
                    processed=0,
                    total=0,
                    duration=duration,
                    missing_ids=missing_ids,
                    metadata=metadata,
                )

            candidates = repository.iter_candidates(
                fast=options.fast,
                changed_since=options.changed_since,
                ids=ids or None,
                batch_size=options.batch_size,
            )
            stream = iter(candidates)
            if skip_count:
                stream = itertools.islice(stream, skip_count, None)

            processed = skip_count
            batch_index = 0

            for batch in _batched(stream, options.batch_size):
                if not batch:
                    continue
                batch_index += 1
                sanitized = [
                    self._sanitize_text((passage.text or "").strip()) for passage in batch
                ]
                batch_start = time.perf_counter()
                try:
                    vectors = self._embedding_service.embed(
                        sanitized, batch_size=options.batch_size
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    raise EmbeddingRebuildError(
                        f"Embedding generation failed: {exc}"
                    ) from exc

                if len(vectors) != len(batch):
                    raise EmbeddingRebuildError(
                        "Embedding backend returned mismatched batch size"
                    )

                updates: list[EmbeddingUpdate] = [
                    EmbeddingUpdate(id=passage.id, embedding=list(vector))
                    for passage, vector in zip(batch, vectors)
                ]
                repository.update_embeddings(updates)
                self._commit_with_retry(session)

                processed += len(batch)
                batch_duration = time.perf_counter() - batch_start
                rate = batch_duration / len(batch)
                state = EmbeddingRebuildState(
                    processed=processed,
                    total=total,
                    last_id=batch[-1].id,
                    metadata=metadata,
                )

                if checkpoint is not None:
                    checkpoint(state)

                if on_progress is not None:
                    on_progress(
                        EmbeddingRebuildProgress(
                            batch_index=batch_index,
                            batch_size=len(batch),
                            batch_duration=batch_duration,
                            rate_per_passage=rate,
                            state=state,
                        )
                    )

            duration = time.perf_counter() - start_time
            return EmbeddingRebuildResult(
                processed=processed,
                total=total,
                duration=duration,
                missing_ids=missing_ids,
                metadata=metadata,
            )
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()

    def _commit_with_retry(self, session: SessionProtocol) -> None:
        for attempt in range(1, self._commit_attempts + 1):
            try:
                session.commit()
            except SQLAlchemyError as exc:  # pragma: no cover - defensive retry path
                rollback = getattr(session, "rollback", None)
                if callable(rollback):
                    rollback()
                if attempt == self._commit_attempts:
                    raise EmbeddingRebuildError(
                        f"Database commit failed after {attempt} attempt(s): {exc}"
                    ) from exc
                time.sleep(self._commit_backoff * attempt)
            else:
                return


def _batched(iterator: Iterable[PassageForEmbedding], size: int) -> Iterable[list[PassageForEmbedding]]:
    while True:
        batch = list(itertools.islice(iterator, size))
        if not batch:
            break
        yield batch


__all__ = [
    "EmbeddingRebuildError",
    "EmbeddingRebuildOptions",
    "EmbeddingRebuildProgress",
    "EmbeddingRebuildResult",
    "EmbeddingRebuildService",
    "EmbeddingRebuildStart",
    "EmbeddingRebuildState",
]
