from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from theo.application.facades.database import Base, configure_engine, get_engine


@pytest.fixture(scope="module")
def worker_db_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a reusable SQLite template with all tables migrated."""

    db_dir = tmp_path_factory.mktemp("worker-template")
    template_path = Path(db_dir) / "template.db"
    configure_engine(f"sqlite:///{template_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)
    engine.dispose()
    return template_path


@pytest.fixture
def worker_engine(tmp_path: Path, worker_db_template: Path):
    """Clone the pre-migrated database for an isolated worker test."""

    db_path = tmp_path / "worker.db"
    shutil.copy(worker_db_template, db_path)
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def worker_session(worker_engine) -> Session:
    """Yield a SQLAlchemy session bound to the prepared worker database."""

    with Session(worker_engine) as session:
        yield session
