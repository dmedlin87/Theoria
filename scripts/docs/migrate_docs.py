#!/usr/bin/env python3
"""Utilities for migrating documentation into the new taxonomy.

The script performs three core actions:

1. Create a timestamped tarball backup of the current ``docs`` directory.
2. Ensure the target taxonomy directory tree exists (based on ``document_taxonomy.json``).
3. Move files according to a JSON migration map.

Usage (from the repository root)::

    python scripts/docs/migrate_docs.py                     # execute migration
    python scripts/docs/migrate_docs.py --dry-run           # preview actions
    python scripts/docs/migrate_docs.py --skip-backup       # skip tarball backup
    python scripts/docs/migrate_docs.py --map custom.json   # custom mapping file

The default migration map lives in ``docs/migrations/document_migration_map.json``
so that future reorganisations can extend or replace it without modifying the
script itself.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
DEFAULT_MAP_PATH = DOCS_ROOT / "migrations" / "document_migration_map.json"
DEFAULT_TAXONOMY_PATH = DOCS_ROOT / "document_taxonomy.json"
BACKUP_DIR = DOCS_ROOT / "backups"


class MigrationError(RuntimeError):
    """Raised when the migration encounters a fatal condition."""


def _load_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover - defensive branch
        raise MigrationError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
        raise MigrationError(f"Invalid JSON in {path}: {exc}") from exc


def load_migration_map(path: Path) -> Mapping[Path, Path]:
    """Load the migration map into ``Path`` objects relative to ``REPO_ROOT``."""

    raw = _load_json(path)
    mapping: dict[Path, Path] = {}
    for source_str, dest_str in raw.items():
        src = (REPO_ROOT / source_str).resolve()
        dest = (REPO_ROOT / dest_str).resolve()
        if src in mapping:
            raise MigrationError(f"Duplicate source path in migration map: {source_str}")
        mapping[src] = dest
    return mapping


def load_expected_directories(path: Path) -> set[Path]:
    """Extract expected directories from the taxonomy configuration."""

    data = _load_json(path)
    expected: set[Path] = set()
    collections = data.get("collections", {})
    for directories in collections.values():
        for directory in directories:
            expected.add((REPO_ROOT / directory).resolve())
    # ``expected_directories`` is optional but provides an escape hatch for
    # callers who want to be explicit.
    for directory in data.get("expected_directories", []):
        expected.add((REPO_ROOT / directory).resolve())
    return expected


def ensure_directories_exist(paths: Iterable[Path], *, dry_run: bool) -> None:
    for path in sorted(paths):
        if dry_run:
            print(f"[dry-run] mkdir -p {path.relative_to(REPO_ROOT)}")
            continue
        path.mkdir(parents=True, exist_ok=True)


def create_docs_backup(*, dry_run: bool) -> Path:
    """Create a tarball backup of the current ``docs`` tree."""

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    tarball = BACKUP_DIR / f"docs-backup-{timestamp}.tar.gz"

    if dry_run:
        print(f"[dry-run] would create backup tarball at {tarball.relative_to(REPO_ROOT)}")
        return tarball

    with tarfile.open(tarball, "w:gz") as archive:
        # Use relative paths inside the tarball to avoid leaking absolute paths.
        archive.add(DOCS_ROOT, arcname="docs")
    print(f"Backup created: {tarball.relative_to(REPO_ROOT)}")
    return tarball


def move_documents(mapping: Mapping[Path, Path], *, dry_run: bool) -> list[str]:
    """Execute the moves described by ``mapping`` and return human logs."""

    logs: list[str] = []
    for source, destination in sorted(mapping.items()):
        if not source.exists():
            raise MigrationError(f"Source document does not exist: {source.relative_to(REPO_ROOT)}")
        if destination.exists():
            raise MigrationError(
                f"Destination already exists: {destination.relative_to(REPO_ROOT)}\n"
                "Refusing to overwrite during migration."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        rel_src = source.relative_to(REPO_ROOT)
        rel_dest = destination.relative_to(REPO_ROOT)
        if dry_run:
            logs.append(f"[dry-run] mv {rel_src} -> {rel_dest}")
            continue
        shutil.move(str(source), str(destination))
        logs.append(f"Moved {rel_src} -> {rel_dest}")
    return logs


def clean_empty_directories(paths: Iterable[Path], *, dry_run: bool) -> list[str]:
    """Remove empty source directories left behind after migration."""

    logs: list[str] = []
    for path in sorted({p.parent for p in paths}, reverse=True):
        if not path.exists():
            continue
        # Skip directories outside the docs tree for safety.
        try:
            path.relative_to(DOCS_ROOT)
        except ValueError:
            continue
        if any(path.iterdir()):
            continue
        if dry_run:
            logs.append(f"[dry-run] rmdir {path.relative_to(REPO_ROOT)}")
            continue
        path.rmdir()
        logs.append(f"Removed empty directory {path.relative_to(REPO_ROOT)}")
    return logs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", dest="map_path", type=Path, default=DEFAULT_MAP_PATH,
                        help="Path to the JSON migration map (default: %(default)s)")
    parser.add_argument(
        "--taxonomy",
        dest="taxonomy_path",
        type=Path,
        default=DEFAULT_TAXONOMY_PATH,
        help="Taxonomy configuration describing the target directory tree (default: %(default)s)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without mutating the filesystem")
    parser.add_argument("--skip-backup", action="store_true", help="Skip creating a tarball backup before migrating")
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Skip pruning empty directories after moving files",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)

    if not DOCS_ROOT.exists():
        print("docs/ directory not found. Are you running from the repository root?", file=sys.stderr)
        return 1

    try:
        migration_map = load_migration_map(options.map_path)
        expected_dirs = load_expected_directories(options.taxonomy_path)
    except MigrationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not options.skip_backup:
        create_docs_backup(dry_run=options.dry_run)
    else:
        print("Skipping docs backup (per --skip-backup)")

    ensure_directories_exist(expected_dirs, dry_run=options.dry_run)

    try:
        move_logs = move_documents(migration_map, dry_run=options.dry_run)
    except MigrationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for line in move_logs:
        print(line)

    if options.no_clean:
        return 0

    cleanup_logs = clean_empty_directories(migration_map.keys(), dry_run=options.dry_run)
    for line in cleanup_logs:
        print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
