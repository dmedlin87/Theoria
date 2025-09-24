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
from theo.services.api.app.db.models import Document  # noqa: E402
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
