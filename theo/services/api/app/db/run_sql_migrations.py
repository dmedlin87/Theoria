"""Execute raw SQL migrations against the configured database engine."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from pathlib import Path
from typing import Iterable

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..core.database import get_engine
from .models import AppSetting

logger = logging.getLogger(__name__)

MIGRATIONS_PATH = Path(__file__).resolve().parent / "migrations"
_MIGRATION_KEY_PREFIX = "db:migration:"


def _iter_migration_files(migrations_path: Path) -> Iterable[Path]:
    if not migrations_path.exists():
        return []
    return sorted(
        path
        for path in migrations_path.iterdir()
        if path.is_file() and path.suffix.lower() == ".sql"
    )


def _migration_key(filename: str) -> str:
    return f"{_MIGRATION_KEY_PREFIX}{filename}"


def run_sql_migrations(
    engine: Engine | None = None,
    migrations_path: Path | None = None,
    *,
    force: bool = False,
) -> list[str]:
    """Apply raw SQL migrations to the active database engine."""

    if engine is None:
        engine = get_engine()

    if migrations_path is None:
        migrations_path = MIGRATIONS_PATH

    dialect_name = getattr(engine.dialect, "name", None)
    if not force and dialect_name != "postgresql":
        logger.debug(
            "Skipping SQL migrations for unsupported dialect: %s", dialect_name
        )
        return []

    applied: list[str] = []
    migration_files = list(_iter_migration_files(migrations_path))
    if not migration_files:
        return applied

    with Session(engine) as session:
        for path in migration_files:
            migration_name = path.name
            key = _migration_key(migration_name)
            if session.get(AppSetting, key):
                continue

            sql = path.read_text(encoding="utf-8")
            if not sql.strip():
                logger.debug("Skipping empty migration file: %s", migration_name)
                session.add(
                    AppSetting(
                        key=key,
                        value={
                            "applied_at": datetime.now(UTC).isoformat(),
                            "filename": migration_name,
                        },
                    )
                )
                applied.append(migration_name)
                continue

            logger.info("Applying SQL migration: %s", migration_name)
            connection = session.connection()
            connection.exec_driver_sql(sql)
            session.add(
                AppSetting(
                    key=key,
                    value={
                        "applied_at": datetime.now(UTC).isoformat(),
                        "filename": migration_name,
                    },
                )
            )
            applied.append(migration_name)

        session.commit()

    return applied
