from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

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

        assert stored.storage_path is not None
        storage_dir = Path(stored.storage_path)
        assert (storage_dir / "content.txt").exists()
        assert (storage_dir / doc_path.name).exists()
        assert (storage_dir / "normalized.json").exists()
        frontmatter_path = storage_dir / "frontmatter.json"
        assert frontmatter_path.exists()
        stored_frontmatter = json.loads(frontmatter_path.read_text("utf-8"))
        assert stored_frontmatter["title"] == "Sample Doc"
        assert stored_frontmatter["authors"] == ["Jane Doe"]
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

        assert stored.storage_path is not None
        storage_dir = Path(stored.storage_path)
        assert (storage_dir / "content.txt").exists()
        assert (storage_dir / "source.html").exists()
        assert (storage_dir / "normalized.json").exists()
        frontmatter_path = storage_dir / "frontmatter.json"
        assert frontmatter_path.exists()
        stored_frontmatter = json.loads(frontmatter_path.read_text("utf-8"))
        assert stored_frontmatter["title"] == "Example"
        assert stored_frontmatter["canonical_url"] == "https://example.com/foo"
    finally:
        settings.storage_root = original_storage


def test_run_pipeline_for_url_rejects_disallowed_scheme(monkeypatch) -> None:
    settings = get_settings()
    original_schemes = list(settings.ingest_url_allowed_schemes)
    settings.ingest_url_allowed_schemes = ["https"]

    def unexpected_fetch(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("Blocked URLs should not be fetched")

    monkeypatch.setattr(pipeline, "_fetch_web_document", unexpected_fetch)

    try:
        with pytest.raises(pipeline.UnsupportedSourceError):
            pipeline.run_pipeline_for_url(object(), "http://example.com/data")
    finally:
        settings.ingest_url_allowed_schemes = original_schemes


def test_run_pipeline_for_url_blocks_private_ip_targets(monkeypatch) -> None:

def test_run_pipeline_for_file_rejects_javascript_source_url(tmp_path) -> None:
    """Unsafe source URLs are stripped during file ingestion."""

    _prepare_database(tmp_path)
    engine = get_engine()

    settings = get_settings()
    original_storage = settings.storage_root
    storage_root = tmp_path / "storage"
    settings.storage_root = storage_root

    try:
        markdown = (
            "---\n"
            "title: Unsafe Doc\n"
            "source_url: \"javascript:alert(1)\"\n"
            "---\n\n"
            "This document links to a javascript URI."
        )
        doc_path = tmp_path / "unsafe.md"
        doc_path.write_text(markdown, encoding="utf-8")

        with Session(engine) as session:
            document = pipeline.run_pipeline_for_file(session, doc_path)
            document_id = document.id

        with Session(engine) as session:
            stored = session.get(Document, document_id)

        assert stored is not None
        assert stored.source_url is None
    finally:
        settings.storage_root = original_storage


def test_run_pipeline_for_transcript_rejects_javascript_source_url(tmp_path) -> None:
    """Unsafe source URLs are stripped during transcript ingestion."""

    _prepare_database(tmp_path)
    engine = get_engine()

    settings = get_settings()
    original_storage = settings.storage_root
    storage_root = tmp_path / "storage"
    settings.storage_root = storage_root

    try:
        transcript_path = tmp_path / "segments.json"
        transcript_payload = [{"text": "Hello world", "start": 0.0, "end": 2.5}]
        transcript_path.write_text(json.dumps(transcript_payload), encoding="utf-8")

        frontmatter = {"title": "Unsafe Transcript", "source_url": "javascript:alert(1)"}

        with Session(engine) as session:
            document = pipeline.run_pipeline_for_transcript(
                session,
                transcript_path,
                frontmatter=frontmatter,
            )
            document_id = document.id

        with Session(engine) as session:
            stored = session.get(Document, document_id)

        assert stored is not None
        assert stored.source_url is None
    finally:
        settings.storage_root = original_storage


@pytest.mark.parametrize(
    "blocked_url",
    [
        "http://localhost/resource",
        "http://10.0.0.12/secret",
    ],
)
def test_run_pipeline_for_url_blocks_private_targets(monkeypatch, blocked_url) -> None:

    def unexpected_fetch(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("Blocked URLs should not be fetched")

    monkeypatch.setattr(pipeline, "_fetch_web_document", unexpected_fetch)

    with pytest.raises(pipeline.UnsupportedSourceError):
        pipeline.run_pipeline_for_url(object(), "https://10.0.0.12/secret")


def test_run_pipeline_for_url_rejects_oversized_responses(monkeypatch) -> None:
    class _StubHeaders:
        def get_content_charset(self) -> str | None:
            return "utf-8"

    class _StubResponse:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload
            self._offset = 0
            self.headers = _StubHeaders()

        def read(self, size: int) -> bytes:
            if self._offset >= len(self._payload):
                return b""
            chunk = self._payload[self._offset : self._offset + size]
            self._offset += len(chunk)
            return chunk

        def geturl(self) -> str:
            return "https://example.com/large"

        def close(self) -> None:
            return None

    class _StubOpener:
        def __init__(self, response: _StubResponse) -> None:
            self._response = response
            self.addheaders: list[tuple[str, str]] = []

        def open(self, request, timeout=None):  # noqa: ANN001
            return self._response

    payload = b"x" * (pipeline._WEB_FETCH_CHUNK_SIZE // 2)
    stub_response = _StubResponse(payload)

    def fake_build_opener(*args, **kwargs):  # noqa: ANN001
        return _StubOpener(stub_response)

    settings = get_settings()
    original_max_bytes = getattr(settings, "ingest_web_max_bytes", None)
    settings.ingest_web_max_bytes = len(payload) // 4

    monkeypatch.setattr(pipeline, "build_opener", fake_build_opener)

    try:
        with pytest.raises(pipeline.UnsupportedSourceError):
            pipeline.run_pipeline_for_url(object(), "https://example.com/large")
    finally:
        settings.ingest_web_max_bytes = original_max_bytes
