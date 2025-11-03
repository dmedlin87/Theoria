import pytest
from sqlalchemy.orm import Session

from theo.application.facades.database import get_settings
from theo.infrastructure.api.app.ingest import pipeline
from theo.infrastructure.api.app.ingest import persistence as ingest_persistence


pytestmark = pytest.mark.pgvector


def test_file_pipeline_records_ingestion(tmp_path, ingest_engine, monkeypatch) -> None:
    engine = ingest_engine

    settings = get_settings()
    original_storage = settings.storage_root
    settings.storage_root = tmp_path / "storage"

    warm_calls: list[bool] = []
    recorded: list[dict[str, object]] = []

    monkeypatch.setattr(ingest_persistence, "_warm_embedding_service", lambda: warm_calls.append(True))

    def _record_document_ingested(**kwargs):
        recorded.append(kwargs)

    monkeypatch.setattr(
        ingest_persistence,
        "_record_document_ingested",
        _record_document_ingested,
    )

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

        assert warm_calls, "expected embedding warmup to run"
        assert recorded, "expected ingestion telemetry to be recorded"

        payload = recorded[-1]
        assert payload["workflow"] == "text"
        assert payload["document_id"] == str(document.id)
        passage_ids = payload["passage_ids"]
        assert isinstance(passage_ids, list)
        assert passage_ids, "expected at least one passage id"
    finally:
        settings.storage_root = original_storage
