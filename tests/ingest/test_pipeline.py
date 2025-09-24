from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.database import (  # noqa: E402  (import after path tweak)
    Base,
    configure_engine,
    get_engine,
    get_settings,
)
from theo.services.api.app.db.models import Document, Passage  # noqa: E402
from theo.services.api.app.ingest import pipeline  # noqa: E402


def _prepare_database(tmp_path: Path) -> None:
    db_path = tmp_path / "pipeline.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_run_pipeline_for_file_persists_chunks(tmp_path) -> None:
    """File ingestion stores a document, passages, and artifacts."""

    _prepare_database(tmp_path)
    engine = get_engine()

    settings = get_settings()
    original_storage = settings.storage_root
    storage_root = tmp_path / "storage"
    settings.storage_root = storage_root

    try:
        markdown = """---\ntitle: Sample Doc\nauthors:\n  - Jane Doe\n---\n\nThis is a sample document."""
        doc_path = tmp_path / "sample.md"
        doc_path.write_text(markdown, encoding="utf-8")

        with Session(engine) as session:
            document = pipeline.run_pipeline_for_file(session, doc_path)
            document_id = document.id

        with Session(engine) as session:
            stored = session.get(Document, document_id)
            passages = session.query(Passage).filter_by(document_id=document_id).all()

        assert stored is not None
        assert stored.title == "Sample Doc"
        assert stored.sha256 is not None
        assert len(passages) >= 1

        storage_dir = Path(stored.storage_path)
        assert (storage_dir / "content.txt").exists()
        assert (storage_dir / doc_path.name).exists()
        assert (storage_dir / "normalized.json").exists()
    finally:
        settings.storage_root = original_storage


def test_run_pipeline_for_url_ingests_html(tmp_path, monkeypatch) -> None:
    """URL ingestion persists HTML content via the generic pipeline."""

    _prepare_database(tmp_path)
    engine = get_engine()

    settings = get_settings()
    original_storage = settings.storage_root
    storage_root = tmp_path / "storage"
    settings.storage_root = storage_root

    def _fake_fetch(settings_obj, url: str):
        html = "<html><head><title>Example</title></head><body><p>Hello world</p></body></html>"
        metadata = {"title": "Example", "canonical_url": url}
        return html, metadata

    monkeypatch.setattr(pipeline, "_fetch_web_document", _fake_fetch)

    try:
        with Session(engine) as session:
            document = pipeline.run_pipeline_for_url(session, "https://example.com/foo")
            document_id = document.id

        with Session(engine) as session:
            stored = session.get(Document, document_id)
            passages = session.query(Passage).filter_by(document_id=document_id).all()

        assert stored is not None
        assert stored.title == "Example"
        assert stored.source_type == "web_page"
        assert stored.source_url == "https://example.com/foo"
        assert len(passages) >= 1

        storage_dir = Path(stored.storage_path)
        assert (storage_dir / "content.txt").exists()
        assert (storage_dir / "source.html").exists()
        assert (storage_dir / "normalized.json").exists()
    finally:
        settings.storage_root = original_storage
