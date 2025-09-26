"""Tests for Celery worker tasks."""

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
from theo.services.api.app.db.models import Document, IngestionJob  # noqa: E402
from theo.services.api.app.workers import tasks  # noqa: E402


def test_process_url_ingests_fixture_url(tmp_path) -> None:
    """The URL worker ingests a YouTube fixture without raising."""

    db_path = tmp_path / "test.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)

    settings = get_settings()
    original_storage = settings.storage_root
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    settings.storage_root = storage_root

    try:
        frontmatter = {
            "title": "Custom Theo Title",
            "collection": "Custom Collection",
        }
        tasks.process_url.run(
            "doc-123",
            "https://youtu.be/sample_video",
            frontmatter=frontmatter,
        )
    finally:
        settings.storage_root = original_storage

    with Session(engine) as session:
        documents = session.query(Document).all()

    assert len(documents) == 1
    document = documents[0]
    assert document.title == "Custom Theo Title"
    assert document.collection == "Custom Collection"
    assert document.channel == "Theo Channel"


def test_enrich_document_populates_metadata(tmp_path) -> None:
    """Metadata enrichment hydrates bibliographic fields from fixtures."""

    db_path = tmp_path / "enrich.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        document = Document(
            title="Theo Engine Sample Work",
            source_type="pdf",
            source_url="https://doi.org/10.1234/sample",
            sha256="sample-sha",
        )
        session.add(document)
        session.commit()
        document_id = document.id

    tasks.enrich_document.run(document_id)

    with Session(engine) as session:
        enriched = session.get(Document, document_id)

    assert enriched is not None
    assert enriched.doi == "10.1234/sample"
    assert enriched.authors == ["Alice Example", "Bob Example"]
    assert enriched.venue == "Journal of Theo Research"
    assert enriched.year == 2022
    assert enriched.abstract == "theo engine research"
    assert enriched.topics == {
        "primary": "Theology",
        "all": ["Theology", "Information Retrieval"],
    }
    assert enriched.enrichment_version == 1
    assert isinstance(enriched.bib_json, dict)
    assert enriched.bib_json.get("enrichment", {}).get("openalex", {}).get("id") == "https://openalex.org/W123456789"
    assert enriched.bib_json.get("primary_topic") == "Theology"


def test_topic_digest_worker_updates_job_status(tmp_path) -> None:
    db_path = tmp_path / "topic.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        job = IngestionJob(job_type="topic_digest", status="queued")
        session.add(job)
        session.commit()
        job_id = job.id

    tasks.topic_digest.run(hours=1, job_id=job_id)

    with Session(engine) as session:
        updated = session.get(IngestionJob, job_id)

    assert updated is not None
    assert updated.status == "completed"
