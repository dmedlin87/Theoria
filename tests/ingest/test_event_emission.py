from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from theo.application.facades.database import (
    Base,
    configure_engine,
    get_engine,
    get_settings,
)
from theo.platform.events import event_bus
from theo.platform.events.types import DocumentIngestedEvent
from theo.services.api.app.ingest import pipeline


def _prepare_database(tmp_path: Path) -> None:
    db_path = tmp_path / "event-bus.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_file_pipeline_emits_document_event(tmp_path) -> None:
    _prepare_database(tmp_path)
    engine = get_engine()

    settings = get_settings()
    original_storage = settings.storage_root
    original_case_builder = settings.case_builder_enabled
    settings.storage_root = tmp_path / "storage"
    settings.case_builder_enabled = True

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
        settings.case_builder_enabled = original_case_builder
