from __future__ import annotations
import pytest
from sqlalchemy.orm import Session

from theo.application.facades.database import (
    get_settings,
)
from theo.platform.events import event_bus
from theo.platform.events.types import DocumentIngestedEvent
from theo.infrastructure.api.app.ingest import pipeline


pytestmark = pytest.mark.pgvector


def test_file_pipeline_emits_document_event(tmp_path, ingest_engine) -> None:
    engine = ingest_engine

    settings = get_settings()
    original_storage = settings.storage_root
    settings.storage_root = tmp_path / "storage"

    captured: list[DocumentIngestedEvent] = []

    def _capture(event: DocumentIngestedEvent) -> None:
        captured.append(event)

    event_bus.subscribe(DocumentIngestedEvent, _capture)

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

        assert captured, "expected a document ingestion event"
        event = captured[-1]
        assert event.document_id == str(document_id)
        assert event.workflow == "text"
        assert len(event.passage_ids) >= 1
    finally:
        event_bus.unsubscribe(DocumentIngestedEvent, _capture)
        settings.storage_root = original_storage
