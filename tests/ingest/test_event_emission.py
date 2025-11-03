from __future__ import annotations
import pytest
from sqlalchemy.orm import Session

from theo.application.facades.database import (
    get_settings,
)
from theo.infrastructure.api.app import events as events_module
from theo.infrastructure.api.app.ingest import pipeline


pytestmark = pytest.mark.pgvector


def test_file_pipeline_emits_document_event(tmp_path, ingest_engine, monkeypatch) -> None:
    engine = ingest_engine

    settings = get_settings()
    original_storage = settings.storage_root
    original_case_builder = settings.case_builder_enabled
    settings.storage_root = tmp_path / "storage"
    settings.case_builder_enabled = True

    captured: list[dict[str, object]] = []

    def _capture(**payload: object) -> None:
        captured.append(payload)

    monkeypatch.setattr(events_module, "notify_document_ingested", _capture)

    try:
        dependencies = pipeline.PipelineDependencies(settings=settings)
        doc_path = tmp_path / "event.md"
        doc_path.write_text("""---\ntitle: Event Test\n---\n\nBody.""", encoding="utf-8")

        with Session(engine) as session:
            document = pipeline.run_pipeline_for_file(
                session,
                doc_path,
                dependencies=dependencies,
            )
            document_id = document.id

        assert captured, "expected a document ingestion notification"
        event = captured[-1]
        assert event["document_id"] == str(document_id)
        assert event["workflow"] == "text"
        assert len(tuple(event.get("passage_ids", ()))) >= 1
    finally:
        settings.storage_root = original_storage
        settings.case_builder_enabled = original_case_builder
