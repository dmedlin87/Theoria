#!/usr/bin/env python3
"""Validate that internal Markdown links resolve to files and anchors."""

from __future__ import annotations

import argparse
import re
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INCLUDE = ["docs", "README.md", "CONTRIBUTING.md", "SECURITY.md", "DEPLOYMENT.md", "START_HERE.md"]
DEFAULT_IGNORE = ["docs/archive/**"]
MARKDOWN_EXTENSIONS = {".md", ".mdx"}
LINK_PATTERN = re.compile(r"(?<![!])\[[^\]]+\]\(([^)]+)\)")
REFERENCE_PATTERN = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)")


def _iter_markdown_files(include: Iterable[str], ignore_globs: Iterable[str]) -> Iterable[Path]:
    ignore_globs = list(ignore_globs)
    seen: set[Path] = set()
    for item in include:
        base = (REPO_ROOT / item).resolve()
        if base.is_dir():
            candidates = base.rglob("*")
        elif base.suffix.lower() in MARKDOWN_EXTENSIONS:
            candidates = [base]
        else:
            continue
        for path in candidates:
            if path in seen:
                continue
            if path.is_dir() or path.suffix.lower() not in MARKDOWN_EXTENSIONS:
                continue
            rel = path.relative_to(REPO_ROOT)
            if any(fnmatch(str(rel), pattern) for pattern in ignore_globs):
                continue
            seen.add(path)
            yield path


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"[^0-9a-z\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _collect_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            if level == 0:
                continue
            heading = stripped[level:].strip()
            if heading:
                anchors.add(_slugify(heading))
    return anchors


def _extract_links(content: str) -> list[str]:
    links = [match.group(1).strip() for match in LINK_PATTERN.finditer(content)]
    for match in REFERENCE_PATTERN.finditer(content):
        links.append(match.group(1).strip())
    return links


def _is_external(target: str) -> bool:
    lower = target.lower()
    return lower.startswith("http://") or lower.startswith("https://") or lower.startswith("mailto:") or lower.startswith("tel:")


def _clean_target(target: str) -> str:
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return target.split("?")[0]


def validate_file(path: Path, cache: dict[Path, set[str]]) -> list[str]:
    errors: list[str] = []
    content = path.read_text(encoding="utf-8")
    anchors = cache.setdefault(path, _collect_anchors(path))
    rel_path = path.relative_to(REPO_ROOT)

    for link in _extract_links(content):
        if not link or link.startswith("#"):
            # pure anchor link within the same document
            target_anchor = link[1:]
            if target_anchor and target_anchor not in anchors:
                errors.append(f"{rel_path}: missing anchor '#{target_anchor}'")
            continue

        if _is_external(link) or link.startswith("data:"):
            continue

        cleaned = _clean_target(link)
        if "#" in cleaned:
            file_part, anchor_part = cleaned.split("#", 1)
        else:
            file_part, anchor_part = cleaned, ""

        target_path = (path.parent / file_part).resolve()
        try:
            target_rel = target_path.relative_to(REPO_ROOT)
        except ValueError:
            errors.append(f"{rel_path}: link '{link}' escapes repository root")
            continue

        if not target_path.exists():
            errors.append(f"{rel_path}: missing target '{target_rel}'")
            continue

        if anchor_part:
            target_anchors = cache.setdefault(target_path, _collect_anchors(target_path))
            anchor_slug = _slugify(anchor_part)
            if anchor_slug not in target_anchors:
                errors.append(f"{rel_path}: missing anchor '#{anchor_part}' in '{target_rel}'")
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", default=DEFAULT_INCLUDE, help="Paths or files to include in the scan")
    parser.add_argument(
        "--ignore",
        dest="ignore",
        action="append",
        default=list(DEFAULT_IGNORE),
        help="Glob pattern to ignore (can be passed multiple times)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    cache: dict[Path, set[str]] = {}
    errors: list[str] = []

    for file_path in _iter_markdown_files(options.paths, options.ignore):
        errors.extend(validate_file(file_path, cache))

    if errors:
        print("Broken documentation links detected:\n", file=sys.stderr)
        for err in sorted(errors):
            print(f"- {err}", file=sys.stderr)
        return 1

    print("All checked documentation links are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
