from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine

from theo.adapters.persistence import Base
from theo.application.facades.database import configure_engine, get_engine


def configure_temporary_engine(path: Path) -> Engine:
    """Configure a throwaway SQLite engine for integration scenarios."""

    database_url = (
        f"sqlite:///{path}" if path.suffix else f"sqlite:///{path / 'db.sqlite'}"
    )
    configure_engine(database_url)
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine


__all__ = ["configure_temporary_engine"]
