"""Command-line entry point for applying raw SQL migrations."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from theo.application.facades.database import configure_engine
from theo.infrastructure.api.app.db.run_sql_migrations import run_sql_migrations


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        dest="database_url",
        help="Database URL to connect to (defaults to Theo settings)",
    )
    parser.add_argument(
        "--path",
        dest="migrations_path",
        type=Path,
        help="Directory containing .sql migration files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apply migrations even when the engine dialect is not PostgreSQL",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    engine = configure_engine(args.database_url)
    applied = run_sql_migrations(
        engine,
        migrations_path=args.migrations_path,
        force=args.force,
    )
    if applied:
        for migration in applied:
            print(f"applied: {migration}")
    else:
        print("no migrations applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
