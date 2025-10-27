#!/usr/bin/env python3
"""Reset the local Theo database, apply migrations, and run a smoke test."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _configure_environment(database_url: str | None, api_key: str) -> None:
    """Ensure settings-dependent environment variables are initialised."""

    os.environ.setdefault("SETTINGS_SECRET_KEY", "local-reset-secret")
    os.environ.setdefault("THEO_DISABLE_AI_SETTINGS", "1")
    api_key_payload = f'["{api_key}"]'
    os.environ["THEO_API_KEYS"] = api_key_payload
    os.environ["API_KEYS"] = api_key_payload
    if database_url:
        os.environ["DATABASE_URL"] = database_url

    from theo.application.facades import settings as settings_module

    settings_module.get_settings.cache_clear()


def _load_settings():
    from theo.application.facades.settings import get_settings

    return get_settings()


def _ensure_models_loaded() -> None:
    """Import model modules so SQLAlchemy metadata is populated."""

    import theo.adapters.persistence.models  # noqa: F401  (side-effect import)


def _run_sql_migrations(engine: Engine, migrations_dir: Path) -> None:
    """Apply raw SQL migrations sequentially."""

    dialect = engine.dialect.name
    if dialect != "postgresql":
        logging.info(
            "Skipping raw SQL migrations for %s databases (PostgreSQL only)", dialect
        )
        return

    if not migrations_dir.exists():
        logging.info("Migration directory %s missing; skipping", migrations_dir)
        return

    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        logging.info("No SQL migrations found under %s", migrations_dir)
        return

    logging.info("Applying %d SQL migration(s)", len(migration_files))
    with engine.begin() as connection:
        for script in migration_files:
            sql = script.read_text(encoding="utf-8").strip()
            if not sql:
                continue
            logging.info("Applying migration %s", script.name)
            connection.exec_driver_sql(sql)


def _seed_reference_data(engine: Engine) -> None:
    from theo.infrastructure.api.app.db.seeds import seed_reference_data

    with Session(bind=engine) as session:
        seed_reference_data(session)


def _reset_schema(engine: Engine) -> None:
    from theo.application.facades.database import Base

    logging.info("Dropping existing tables")
    Base.metadata.drop_all(bind=engine)
    logging.info("Recreating tables")
    Base.metadata.create_all(bind=engine)


def _run_smoke_test(api_key: str, osis_reference: str) -> None:
    from theo.infrastructure.api.app.bootstrap import create_app

    logging.info("Running smoke test against /research/contradictions")
    with TestClient(create_app()) as client:
        response = client.get(
            "/research/contradictions",
            params={"osis": osis_reference, "limit": 1},
            headers={"X-API-Key": api_key},
        )
        response.raise_for_status()
        payload = response.json()
        item_count = len(payload.get("items", [])) if isinstance(payload, dict) else None
        logging.info(
            "Smoke test succeeded (status=%s, items=%s)",
            response.status_code,
            item_count,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Drop and recreate Theo Engine database tables, run SQL migrations, "
            "seed reference datasets, and verify the API returns seeded data."
        )
    )
    parser.add_argument(
        "--database-url",
        dest="database_url",
        help="Optional SQLAlchemy database URL override (defaults to configured settings)",
    )
    parser.add_argument(
        "--migrations-path",
        dest="migrations_path",
        type=Path,
        help="Directory containing raw SQL migration files (defaults to bundled migrations)",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default="local-reset-key",
        help="API key used for the authenticated smoke test",
    )
    parser.add_argument(
        "--osis",
        dest="osis",
        default="John.3.16",
        help="OSIS reference to include in the smoke-test query",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="INFO",
        help="Logging verbosity (DEBUG, INFO, WARNING, ERROR)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    _configure_environment(args.database_url, args.api_key)
    settings = _load_settings()

    from theo.application.facades.database import configure_engine

    engine = configure_engine(settings.database_url)

    migrations_dir = args.migrations_path or (
        PROJECT_ROOT / "theo" / "services" / "api" / "app" / "db" / "migrations"
    )

    _ensure_models_loaded()
    _reset_schema(engine)
    _run_sql_migrations(engine, migrations_dir)
    _seed_reference_data(engine)
    _run_smoke_test(args.api_key, args.osis)

    logging.info("Reset + reseed complete")


if __name__ == "__main__":
    main()
