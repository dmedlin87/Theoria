#!/usr/bin/env python3
"""Lightweight governance checks for documentation and bug ledgers.

Usage:
    python scripts/check_docs_governance.py

Exits with non-zero status if:
    * A canonical doc listed in FEATURE_INDEX.md cannot be found.
    * A status value is not in the approved set.
    * The known bugs ledger references an impacted doc that does not exist.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURE_INDEX = REPO_ROOT / "docs" / "status" / "FEATURE_INDEX.md"
KNOWN_BUGS = REPO_ROOT / "docs" / "status" / "KnownBugs.md"

VALID_STATUSES = {"Planned", "Active", "Stable", "Deprecated"}
VALID_BUG_STATUSES = {"Open", "In Progress", "Resolved"}


@dataclass
class FeatureEntry:
    feature: str
    path: Path
    owner: str
    last_reviewed: str
    status: str
    notes: str


@dataclass
class BugEntry:
    bug_id: str
    status: str
    impacted_raw: str


def _parse_table(markdown_path: Path) -> list[list[str]]:
    """Parse a GitHub-flavored Markdown table into rows (excluding header separator)."""
    lines = markdown_path.read_text(encoding="utf-8").strip().splitlines()
    table_lines = []
    capture = False
    for line in lines:
        if line.startswith("|"):
            capture = True
            table_lines.append(line)
        elif capture:
            # stop at first non-table line after table
            break
    reader = csv.reader(table_lines, delimiter="|")
    rows = [list(map(str.strip, row[1:-1])) for row in reader]
    # Skip header + separator
    return rows[2:]


def load_feature_entries() -> list[FeatureEntry]:
    rows = _parse_table(FEATURE_INDEX)
    entries = []
    for row in rows:
        if len(row) < 6:
            continue
        feature, doc_path, owner, last_reviewed, status, notes = row[:6]
        entries.append(
            FeatureEntry(
                feature=feature,
                path=Path(doc_path.strip("`")),
                owner=owner,
                last_reviewed=last_reviewed,
                status=status,
                notes=notes,
            )
        )
    return entries


def load_bug_entries() -> list[BugEntry]:
    rows = _parse_table(KNOWN_BUGS)
    bugs = []
    for row in rows:
        if not row or row[0] == "_None_":
            continue
        bug_id, _title, _severity, status, _owner, _first, _updated, impacted_docs, _link = row[
            :9
        ]
        bugs.append(
            BugEntry(
                bug_id=bug_id,
                status=status,
                impacted_raw=impacted_docs,
            )
        )
    return bugs


def validate_features(entries: list[FeatureEntry]) -> list[str]:
    errors = []
    for entry in entries:
        if entry.status not in VALID_STATUSES:
            errors.append(
                f"[FEATURE_INDEX] Invalid status '{entry.status}' for feature '{entry.feature}'."
            )
        doc_path = REPO_ROOT / entry.path
        if not doc_path.exists():
            errors.append(
                f"[FEATURE_INDEX] Canonical doc '{entry.path}' for feature '{entry.feature}' is missing."
            )
    return errors


def validate_bugs(entries: list[BugEntry]) -> list[str]:
    errors = []
    for bug in entries:
        if bug.status not in VALID_BUG_STATUSES:
            errors.append(f"[KnownBugs] Invalid status '{bug.status}' for bug '{bug.bug_id}'.")
        impacted = [part.strip() for part in bug.impacted_raw.split(",") if part.strip()]
        for doc in impacted:
            doc_path = REPO_ROOT / doc.strip("`")
            if not doc_path.exists():
                errors.append(
                    f"[KnownBugs] Impacted doc '{doc}' listed for bug '{bug.bug_id}' does not exist."
                )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    if not FEATURE_INDEX.exists():
        print("Feature index not found at expected location.", file=sys.stderr)
        return 1
    if not KNOWN_BUGS.exists():
        print("Known bugs ledger not found at expected location.", file=sys.stderr)
        return 1

    errors = []
    errors.extend(validate_features(load_feature_entries()))
    errors.extend(validate_bugs(load_bug_entries()))

    if errors:
        print("Documentation governance checks failed:\n", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print("Documentation governance checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
