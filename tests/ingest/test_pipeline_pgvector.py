from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from theo.application.facades.settings import get_settings
from theo.infrastructure.api.app.ingest import pipeline
from theo.infrastructure.api.app.ingest.exceptions import UnsupportedSourceError
from theo.infrastructure.api.app.ingest.stages import ErrorDecision, ErrorPolicy, IngestContext
from theo.infrastructure.api.app.persistence_models import Document, Passage
from theo.infrastructure.api.app.ingest import persistence as ingest_persistence


class _StubEmbeddingService:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 0.0, 0.0] for _ in texts]


def _capture_span_attributes(monkeypatch: pytest.MonkeyPatch):
    recorded: list[tuple[Any, str, Any]] = []

    def _record(span: Any, key: str, value: Any) -> None:
        recorded.append((span, key, value))

    monkeypatch.setattr(pipeline, "set_span_attribute", _record)
    return recorded


def _record_persistence_events(monkeypatch: pytest.MonkeyPatch):
    published: list[Any] = []
    emitted: list[dict[str, Any]] = []

    original_publish = ingest_persistence.event_bus.publish

    def _publish(event: Any, *args, **kwargs):  # noqa: ANN001
        published.append(event)
        return original_publish(event, *args, **kwargs)

    def _emit_document_persisted_event(*, document, passages, **kwargs):  # noqa: ANN001
        payload = {
            "document_id": str(document.id),
            "passage_count": len(passages),
            "metadata": kwargs.get("metadata", {}),
        }
        emitted.append(payload)
        return SimpleNamespace(**payload)

    monkeypatch.setattr(ingest_persistence.event_bus, "publish", _publish)
    monkeypatch.setattr(
        ingest_persistence, "emit_document_persisted_event", _emit_document_persisted_event
    )
    return published, emitted


def _build_dependencies(settings) -> pipeline.PipelineDependencies:
    return pipeline.PipelineDependencies(
        settings=settings,
        embedding_service=_StubEmbeddingService(),
    )


def _write_markdown(path: Path, title: str, body: str) -> None:
    frontmatter = f"---\ntitle: {title}\n---\n\n"
    path.write_text(frontmatter + body, encoding="utf-8")


@pytest.mark.pgvector
def test_pgvector_malformed_pdf_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pgvector_pipeline_session_factory,
) -> None:
    settings = get_settings()
    original_storage = settings.storage_root
    settings.storage_root = tmp_path / "storage"

    recorded = _capture_span_attributes(monkeypatch)
    published, emitted = _record_persistence_events(monkeypatch)

    broken_pdf = tmp_path / "malformed.pdf"
    broken_pdf.write_bytes(b"%PDF-1.4\n%broken payload")

    dependencies = _build_dependencies(settings)

    session = pgvector_pipeline_session_factory()
    try:
        with pytest.raises(UnsupportedSourceError):
            pipeline.run_pipeline_for_file(session, broken_pdf, dependencies=dependencies)
        session.rollback()

        assert session.query(Document).count() == 0
    finally:
        session.close()
        settings.storage_root = original_storage

    assert published == []
    assert emitted == []

    source_types = [value for _, key, value in recorded if key == "ingest.source_type"]
    assert source_types and source_types[-1] == "pdf"


@pytest.mark.pgvector
def test_pgvector_large_file_records_chunk_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pgvector_pipeline_session_factory,
) -> None:
    settings = get_settings()
    original_storage = settings.storage_root
    settings.storage_root = tmp_path / "storage"

    recorded = _capture_span_attributes(monkeypatch)
    published, emitted = _record_persistence_events(monkeypatch)

    paragraphs = []
    token_block = " ".join(f"token{i}" for i in range(300))
    for index in range(200):
        paragraphs.append(f"Paragraph {index}. {token_block}.")
    body = "\n\n".join(paragraphs)

    doc_path = tmp_path / "large.md"
    _write_markdown(doc_path, "Large Document", body)

    dependencies = _build_dependencies(settings)

    session = pgvector_pipeline_session_factory()
    try:
        document = pipeline.run_pipeline_for_file(
            session,
            doc_path,
            dependencies=dependencies,
        )
        session.flush()
        passage_count = session.query(Passage).filter_by(document_id=document.id).count()
        assert passage_count > 32
    finally:
        session.close()
        settings.storage_root = original_storage

    span_metrics: dict[Any, dict[str, Any]] = {}
    for span, key, value in recorded:
        span_metrics.setdefault(span, {})[key] = value

    ingest_metrics = next(
        metrics for metrics in span_metrics.values() if metrics.get("ingest.document_id")
    )
    assert ingest_metrics["ingest.chunk_count"] == passage_count
    assert ingest_metrics["ingest.batch_size"] == 32
    assert ingest_metrics["ingest.document_id"] == document.id

    assert published and published[0].workflow == "text"
    assert emitted and emitted[0]["passage_count"] == passage_count


@pytest.mark.pgvector
def test_pgvector_concurrent_ingestion_isolated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pgvector_pipeline_engine,
) -> None:
    settings = get_settings()
    original_storage = settings.storage_root
    settings.storage_root = tmp_path / "storage"

    recorded = _capture_span_attributes(monkeypatch)
    published, emitted = _record_persistence_events(monkeypatch)

    session_factory = sessionmaker(bind=pgvector_pipeline_engine, future=True)

    dependencies = _build_dependencies(settings)

    paths: list[Path] = []
    for index in range(2):
        body = f"Concurrent body {index}." * 20
        path = tmp_path / f"concurrent-{index}.md"
        _write_markdown(path, f"Concurrent {index}", body)
        paths.append(path)

    def _ingest(path: Path):
        session = session_factory()
        try:
            document = pipeline.run_pipeline_for_file(
                session,
                path,
                dependencies=dependencies,
            )
            session.flush()
            count = session.query(Passage).filter_by(document_id=document.id).count()
            return document.id, count
        finally:
            session.rollback()
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(_ingest, paths))
    finally:
        settings.storage_root = original_storage

    doc_ids = {doc_id for doc_id, _ in results}
    assert len(doc_ids) == 2
    for _, count in results:
        assert count >= 1

    cleanup = session_factory()
    try:
        if doc_ids:
            cleanup.execute(delete(Passage).where(Passage.document_id.in_(doc_ids)))
            cleanup.execute(delete(Document).where(Document.id.in_(doc_ids)))
            cleanup.commit()
    finally:
        cleanup.close()

    span_metrics: dict[Any, dict[str, Any]] = {}
    for span, key, value in recorded:
        if key.startswith("ingest."):
            span_metrics.setdefault(span, {})[key] = value

    seen_ids = {
        metrics.get("ingest.document_id")
        for metrics in span_metrics.values()
        if "ingest.document_id" in metrics
    }
    assert doc_ids <= seen_ids

    assert len(published) >= 2
    assert len(emitted) >= 2


class _RetryingPolicy(ErrorPolicy):
    def __init__(self) -> None:
        self.decisions: list[tuple[str, int]] = []

    def decide(
        self,
        *,
        stage: str,
        error: Exception,
        attempt: int,
        context: IngestContext,
    ) -> ErrorDecision:
        if stage == "text_document_persister" and attempt == 1:
            self.decisions.append((stage, attempt))
            return ErrorDecision(retry=True, max_retries=1)
        return ErrorDecision()


@pytest.mark.pgvector
def test_pgvector_pipeline_recovers_from_transient_persist_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pgvector_pipeline_session_factory,
) -> None:
    settings = get_settings()
    original_storage = settings.storage_root
    settings.storage_root = tmp_path / "storage"

    recorded = _capture_span_attributes(monkeypatch)
    published, emitted = _record_persistence_events(monkeypatch)

    attempts = {"count": 0}
    original_persist = pipeline.TextDocumentPersister.persist

    def _flaky_persist(self, *, context, state):  # noqa: ANN001
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient failure")
        return original_persist(self, context=context, state=state)

    monkeypatch.setattr(pipeline.TextDocumentPersister, "persist", _flaky_persist)

    doc_path = tmp_path / "retry.md"
    _write_markdown(doc_path, "Retry Document", "Retry body content.")

    policy = _RetryingPolicy()
    dependencies = pipeline.PipelineDependencies(
        settings=settings,
        embedding_service=_StubEmbeddingService(),
        error_policy=policy,
    )

    session = pgvector_pipeline_session_factory()
    try:
        document = pipeline.run_pipeline_for_file(
            session,
            doc_path,
            dependencies=dependencies,
        )
        session.flush()
        stored = session.get(Document, document.id)
        assert stored is not None
    finally:
        session.close()
        settings.storage_root = original_storage

    assert attempts["count"] == 2
    assert policy.decisions == [("text_document_persister", 1)]

    span_metrics: dict[Any, dict[str, Any]] = {}
    for span, key, value in recorded:
        span_metrics.setdefault(span, {})[key] = value

    ingest_metrics = next(
        metrics for metrics in span_metrics.values() if metrics.get("ingest.document_id")
    )
    assert ingest_metrics["ingest.chunk_count"] >= 1
    assert ingest_metrics["ingest.cache_status"] == "n/a"

    assert published and published[0].workflow == "text"
    assert emitted and emitted[0]["document_id"] == document.id

