"""Case builder integration tests for annotations."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
    get_settings,
)
from theo.services.api.app.db.models import CaseObject, Document  # noqa: E402
from theo.services.api.app.ingest import pipeline  # noqa: E402
from theo.services.api.app.models.documents import (  # noqa: E402
    DocumentAnnotationCreate,
)
from theo.services.api.app.retriever import documents as documents_api  # noqa: E402


def _prepare_database(tmp_path: Path) -> None:
    db_path = tmp_path / "annotations.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_create_annotation_persists_case_object(tmp_path) -> None:
    """Annotations are mirrored into CaseObject rows when enabled."""

    _prepare_database(tmp_path)
    engine = get_engine()

    settings = get_settings()
    original_storage = settings.storage_root
    original_flag = settings.case_builder_enabled
    settings.storage_root = tmp_path / "storage"
    settings.case_builder_enabled = True

    try:
        markdown = "---\ntitle: Annotated Doc\n---\n\nInitial passage text."
        doc_path = tmp_path / "annotated.md"
        doc_path.write_text(markdown, encoding="utf-8")

        with Session(engine) as session:
            document = pipeline.run_pipeline_for_file(session, doc_path)
            document_id = document.id

        payload = DocumentAnnotationCreate(body="Important analyst note")

        with Session(engine) as session:
            response = documents_api.create_annotation(session, document_id, payload)
            case_object = (
                session.query(CaseObject)
                .filter(CaseObject.annotation_id == response.id)
                .one_or_none()
            )
            stored_document = session.get(Document, document_id)

        assert case_object is not None
        assert case_object.object_type == "annotation"
        assert case_object.document_id == document_id
        assert case_object.embedding is not None
        assert stored_document is not None
    finally:
        settings.storage_root = original_storage
        settings.case_builder_enabled = original_flag
