#!/usr/bin/env python3
"""Report Markdown files that do not belong to the documented taxonomy."""

from __future__ import annotations

import argparse
import json
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TAXONOMY = REPO_ROOT / "docs" / "document_taxonomy.json"
DEFAULT_EXTENSIONS = {".md", ".mdx"}


def _load_taxonomy(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Taxonomy configuration not found: {path}") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Invalid taxonomy JSON: {exc}") from exc


def _normalise_paths(paths: Iterable[str]) -> set[Path]:
    normalised: set[Path] = set()
    for raw in paths:
        normalised.add((REPO_ROOT / raw).resolve())
    return normalised


def _collect_allowed_paths(taxonomy: dict) -> tuple[set[Path], set[str]]:
    root_docs = _normalise_paths(taxonomy.get("root_documents", []))
    directories: set[Path] = set()
    for directory_list in taxonomy.get("collections", {}).values():
        directories |= _normalise_paths(directory_list)
    directories |= _normalise_paths(taxonomy.get("expected_directories", []))
    ignored = set(taxonomy.get("ignored_globs", []))
    return root_docs | directories, ignored


def _is_allowed(path: Path, allowed_paths: set[Path], ignored_globs: set[str], extensions: set[str]) -> bool:
    if path.suffix.lower() not in extensions:
        return True

    rel = path.relative_to(REPO_ROOT)
    rel_str = str(rel)
    if any(fnmatch(rel_str, pattern) for pattern in ignored_globs):
        return True

    if path in allowed_paths:
        return True

    for allowed in allowed_paths:
        if allowed.is_dir():
            try:
                path.relative_to(allowed)
            except ValueError:
                continue
            else:
                return True
    return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY,
                        help="Path to document_taxonomy.json")
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=sorted(DEFAULT_EXTENSIONS),
        help="File extensions to consider (default: %(default)s)",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["docs"],
        help="Directories to inspect for orphaned documents",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)

    try:
        taxonomy = _load_taxonomy(options.taxonomy)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    allowed_paths, ignored_globs = _collect_allowed_paths(taxonomy)
    extensions = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in options.extensions}

    orphans: list[str] = []
    for entry in options.paths:
        base = (REPO_ROOT / entry).resolve()
        if not base.exists():
            print(f"Warning: path does not exist: {entry}", file=sys.stderr)
            continue
        for file_path in base.rglob("*"):
            if file_path.is_dir():
                continue
            if not _is_allowed(file_path.resolve(), allowed_paths, ignored_globs, extensions):
                orphans.append(str(file_path.relative_to(REPO_ROOT)))

    if orphans:
        print("Orphaned documentation files detected:\n", file=sys.stderr)
        for orphan in sorted(orphans):
            print(f"- {orphan}", file=sys.stderr)
        return 1

    print("No orphaned documentation files detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
