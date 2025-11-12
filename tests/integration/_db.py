from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

try:  # pragma: no cover - optional dependency guard
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session
except (ModuleNotFoundError, ImportError):  # pragma: no cover - lightweight envs
    Engine = Session = object  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency guard
    from theo.adapters.persistence import Base
    from theo.application.facades.database import configure_engine, get_engine
    from theo.infrastructure.api.app.persistence_models import Document as DocumentRecord
    from theo.infrastructure.api.app.persistence_models import Passage
except (ModuleNotFoundError, ImportError):  # pragma: no cover - lightweight envs
    Base = None  # type: ignore[assignment]
    configure_engine = get_engine = None  # type: ignore[assignment]
    DocumentRecord = Passage = None  # type: ignore[assignment]

_DUPLICATE_BASELINE_SHA = "integration-duplicate-baseline"


def ensure_duplicate_detection_baseline(session: Session) -> None:
    """Insert a deterministic record used for duplicate detection checks."""

    if DocumentRecord is None or Passage is None or Session is object:
        return

    existing = (
        session.query(DocumentRecord.id)
        .filter(DocumentRecord.sha256 == _DUPLICATE_BASELINE_SHA)
        .first()
    )
    if existing is not None:
        return

    now = datetime(2020, 1, 1, tzinfo=timezone.utc)
    document = DocumentRecord(
        id="integration-duplicate-baseline-doc",
        title="Integration Duplicate Baseline",
        collection="integration-baseline",
        sha256=_DUPLICATE_BASELINE_SHA,
        created_at=now,
        updated_at=now,
    )
    session.add(document)
    session.flush()
    session.add(
        Passage(
            id="integration-duplicate-baseline-passage",
            document_id=document.id,
            text="Baseline duplicate detection passage.",
            raw_text="Baseline duplicate detection passage.",
            tokens=5,
        )
    )
    session.flush()


def configure_temporary_engine(path: Path) -> Engine:
    """Configure a throwaway SQLite engine for integration scenarios."""

    if (
        Engine is object
        or Base is None
        or configure_engine is None
        or get_engine is None
    ):
        pytest.skip("sqlalchemy not installed")

    database_url = (
        f"sqlite:///{path}" if path.suffix else f"sqlite:///{path / 'db.sqlite'}"
    )
    configure_engine(database_url)
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        ensure_duplicate_detection_baseline(session)
        session.commit()
    return engine


__all__ = ["configure_temporary_engine", "ensure_duplicate_detection_baseline"]
