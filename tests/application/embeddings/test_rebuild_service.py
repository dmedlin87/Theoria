from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

import pytest
from sqlalchemy.exc import SQLAlchemyError

from theo.application.embeddings import (
    EmbeddingRebuildError,
    EmbeddingRebuildOptions,
    EmbeddingRebuildProgress,
    EmbeddingRebuildService,
    EmbeddingRebuildStart,
    EmbeddingRebuildState,
)
from theo.application.interfaces import SessionProtocol
from theo.application.repositories.embedding_repository import (
    EmbeddingUpdate,
    PassageEmbeddingRepository,
    PassageForEmbedding,
)


@dataclass
class FakePassage:
    id: str
    text: str
    embedding: list[float] | None
    document_updated_at: datetime | None = None


class FakeSession(SessionProtocol):
    def __init__(self, should_fail: bool = False) -> None:
        self.bulk_updates: list[list[EmbeddingUpdate]] = []
        self.commits = 0
        self.rollbacks = 0
        self.should_fail = should_fail
        self._failures_remaining = 1 if should_fail else 0
        self.closed = False

    def get(self, entity: type, ident: object, /, **kwargs: object) -> object | None:  # pragma: no cover - unused
        return None

    def add(self, instance: object, /, **kwargs: object) -> None:  # pragma: no cover - unused
        return None

    def commit(self) -> None:
        if self._failures_remaining > 0:
            self._failures_remaining -= 1
            self.rollbacks += 1
            raise SQLAlchemyError("commit failed")
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class FakeRepository(PassageEmbeddingRepository):
    def __init__(self, passages: list[FakePassage]) -> None:
        self.passages = passages
        self.updated: list[EmbeddingUpdate] = []

    def count_candidates(
        self,
        *,
        fast: bool,
        changed_since: datetime | None,
        ids: Sequence[str] | None,
    ) -> int:
        return len(list(self._filter(passages=self.passages, fast=fast, changed_since=changed_since, ids=ids)))

    def existing_ids(self, ids: Sequence[str]) -> set[str]:
        id_set = set(ids)
        return {passage.id for passage in self.passages if passage.id in id_set}

    def iter_candidates(
        self,
        *,
        fast: bool,
        changed_since: datetime | None,
        ids: Sequence[str] | None,
        batch_size: int,
    ) -> Iterable[PassageForEmbedding]:
        for passage in self._filter(passages=self.passages, fast=fast, changed_since=changed_since, ids=ids):
            yield PassageForEmbedding(
                id=passage.id,
                text=passage.text,
                embedding=passage.embedding,
                document_updated_at=passage.document_updated_at,
            )

    def update_embeddings(self, updates: Sequence[EmbeddingUpdate]) -> None:
        self.updated.extend(updates)
        for update in updates:
            for passage in self.passages:
                if passage.id == update.id:
                    passage.embedding = list(update.embedding)
                    break

    def _filter(
        self,
        *,
        passages: list[FakePassage],
        fast: bool,
        changed_since: datetime | None,
        ids: Sequence[str] | None,
    ) -> Iterable[FakePassage]:
        for passage in sorted(passages, key=lambda item: item.id):
            if fast and passage.embedding is not None:
                continue
            if changed_since is not None:
                updated = passage.document_updated_at
                if updated is None or updated < changed_since:
                    continue
            if ids and passage.id not in ids:
                continue
            yield passage


class FakeEmbeddingBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], int]] = []
        self.responses: list[list[list[float]]] = []

    def queue(self, vectors: list[list[float]]) -> None:
        self.responses.append(vectors)

    def embed(self, texts: Sequence[str], *, batch_size: int) -> Sequence[Sequence[float]]:
        self.calls.append((tuple(texts), batch_size))
        if self.responses:
            return self.responses.pop(0)
        return [[float(index)] for index, _ in enumerate(texts)]


def sanitize(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture()
def passages() -> list[FakePassage]:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        FakePassage(id="p1", text=" First passage ", embedding=None, document_updated_at=now),
        FakePassage(id="p2", text="Second", embedding=None, document_updated_at=now),
    ]


@pytest.fixture()
def service(passages: list[FakePassage]) -> tuple[EmbeddingRebuildService, FakeEmbeddingBackend, FakeSession]:
    backend = FakeEmbeddingBackend()
    backend.queue([[0.1, 0.2], [0.2, 0.3]])
    session = FakeSession()
    repository = FakeRepository(passages)

    def session_factory() -> SessionProtocol:
        return session

    def repository_factory(_session: SessionProtocol) -> PassageEmbeddingRepository:
        return repository

    svc = EmbeddingRebuildService(
        session_factory=session_factory,
        repository_factory=repository_factory,
        embedding_service=backend,
        sanitize_text=sanitize,
    )
    return svc, backend, session


def test_service_rebuilds_embeddings_with_progress(service: tuple[EmbeddingRebuildService, FakeEmbeddingBackend, FakeSession], passages: list[FakePassage]) -> None:
    svc, backend, session = service
    options = EmbeddingRebuildOptions(fast=False, batch_size=2)
    starts: list[EmbeddingRebuildStart] = []
    progress_events: list[EmbeddingRebuildProgress] = []

    result = svc.rebuild_embeddings(
        options,
        on_start=starts.append,
        on_progress=progress_events.append,
    )

    assert result.processed == 2
    assert session.commits == 1
    assert backend.calls[0][0] == ("First passage", "Second")
    assert passages[0].embedding == [0.1, 0.2]
    assert passages[1].embedding == [0.2, 0.3]
    assert starts and starts[0].total == 2
    assert progress_events and progress_events[0].state.processed == 2


def test_service_filters_by_ids_and_reports_missing(passages: list[FakePassage]) -> None:
    backend = FakeEmbeddingBackend()
    backend.queue([[0.5, 0.6]])
    session = FakeSession()
    repository = FakeRepository(passages)

    service = EmbeddingRebuildService(
        session_factory=lambda: session,
        repository_factory=lambda _session: repository,
        embedding_service=backend,
        sanitize_text=sanitize,
    )

    options = EmbeddingRebuildOptions(fast=False, batch_size=1, ids=["p2", "missing"], skip_count=0)
    starts: list[EmbeddingRebuildStart] = []

    result = service.rebuild_embeddings(
        options,
        on_start=starts.append,
    )

    assert starts[0].missing_ids == ["missing"]
    assert result.processed == 1
    assert backend.calls[0][0] == ("Second",)


def test_service_respects_skip_count(passages: list[FakePassage]) -> None:
    backend = FakeEmbeddingBackend()
    backend.queue([[1.0, 1.0]])
    session = FakeSession()
    repository = FakeRepository(passages)

    service = EmbeddingRebuildService(
        session_factory=lambda: session,
        repository_factory=lambda _session: repository,
        embedding_service=backend,
        sanitize_text=sanitize,
    )

    options = EmbeddingRebuildOptions(fast=False, batch_size=1, skip_count=1)

    result = service.rebuild_embeddings(options)

    assert result.processed == 2
    assert len(backend.calls) == 1
    assert backend.calls[0][0] == ("Second",)


def test_service_handles_no_candidates(passages: list[FakePassage]) -> None:
    backend = FakeEmbeddingBackend()
    session = FakeSession()
    repository = FakeRepository(passages)

    for passage in passages:
        passage.embedding = [0.0]

    service = EmbeddingRebuildService(
        session_factory=lambda: session,
        repository_factory=lambda _session: repository,
        embedding_service=backend,
        sanitize_text=sanitize,
    )

    options = EmbeddingRebuildOptions(fast=True, batch_size=1)

    result = service.rebuild_embeddings(options)

    assert result.total == 0
    assert session.commits == 0


def test_service_raises_on_backend_mismatch(passages: list[FakePassage]) -> None:
    backend = FakeEmbeddingBackend()
    backend.queue([[1.0]])  # fewer vectors than passages in batch
    session = FakeSession()
    repository = FakeRepository(passages)

    service = EmbeddingRebuildService(
        session_factory=lambda: session,
        repository_factory=lambda _session: repository,
        embedding_service=backend,
        sanitize_text=sanitize,
    )

    options = EmbeddingRebuildOptions(fast=False, batch_size=2)

    with pytest.raises(EmbeddingRebuildError):
        service.rebuild_embeddings(options)


def test_service_clears_cache_when_requested(passages: list[FakePassage]) -> None:
    backend = FakeEmbeddingBackend()
    backend.queue([[0.1]])
    session = FakeSession()
    repository = FakeRepository(passages)
    cleared: list[bool] = []

    service = EmbeddingRebuildService(
        session_factory=lambda: session,
        repository_factory=lambda _session: repository,
        embedding_service=backend,
        sanitize_text=sanitize,
        cache_clearer=lambda: cleared.append(True),
    )

    options = EmbeddingRebuildOptions(fast=False, batch_size=1, clear_cache=True)

    service.rebuild_embeddings(options)

    assert cleared == [True]


def test_service_retries_commits(passages: list[FakePassage]) -> None:
    backend = FakeEmbeddingBackend()
    backend.queue([[0.1]])
    session = FakeSession(should_fail=True)
    repository = FakeRepository(passages)

    service = EmbeddingRebuildService(
        session_factory=lambda: session,
        repository_factory=lambda _session: repository,
        embedding_service=backend,
        sanitize_text=sanitize,
    )

    options = EmbeddingRebuildOptions(fast=False, batch_size=1)

    result = service.rebuild_embeddings(options)

    assert result.processed == 2
    assert session.commits == 2
    assert session.rollbacks >= 1
    assert session.closed
