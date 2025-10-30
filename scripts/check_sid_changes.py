#!/usr/bin/env python3
"""Validate Security Incident Document (SID) coverage for code changes.

The script inspects the git diff for the current working tree (or a
configurable revision range) and determines whether any Security Incident
Documents (SIDs) were updated. When watchlist entries match files that
changed, the corresponding SID updates become mandatory. The watchlist is a
YAML file containing path globs and optional explicit SID identifiers.

The checker is intentionally lightweight so it can run in developer
workstations, pre-commit hooks, or CI jobs without additional dependencies.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Sequence

import yaml


SID_PATTERN = re.compile(r"\bSID[-_\s]?(\d{3,})\b", re.IGNORECASE)
DEFAULT_WATCHLIST_PATH = Path("docs/security/sid_watchlist.yaml")


class SidCheckError(RuntimeError):
    """Raised when the SID checks fail."""


@dataclass(slots=True)
class WatchlistEntry:
    """In-memory representation of a watchlist rule."""

    name: str
    patterns: Sequence[str]
    require_sid: bool = True
    required_sids: set[str] = field(default_factory=set)
    sid_paths: Sequence[str] = field(default_factory=tuple)
    description: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> "WatchlistEntry":
        if "patterns" not in data:
            raise ValueError("Watchlist entry is missing required 'patterns' key")

        name = str(data.get("name") or ", ".join(map(str, data["patterns"])))
        raw_patterns = data["patterns"]
        if isinstance(raw_patterns, str):
            patterns: List[str] = [raw_patterns]
        elif isinstance(raw_patterns, Iterable):
            patterns = [str(pattern) for pattern in raw_patterns]
        else:
            raise ValueError("'patterns' must be a string or iterable of strings")

        require_sid = bool(data.get("require_sid", True))

        raw_required = data.get("required_sids", [])
        required_sids: set[str]
        if isinstance(raw_required, str):
            required_sids = {normalise_sid(raw_required)}
        elif isinstance(raw_required, Iterable):
            required_sids = {normalise_sid(str(item)) for item in raw_required}
        else:
            raise ValueError("'required_sids' must be a string or iterable of strings")

        raw_sid_paths = data.get("sid_paths", [])
        if isinstance(raw_sid_paths, str):
            sid_paths: Sequence[str] = (raw_sid_paths,)
        elif isinstance(raw_sid_paths, Iterable):
            sid_paths = tuple(str(item) for item in raw_sid_paths)
        else:
            raise ValueError("'sid_paths' must be a string or iterable of strings")

        description = str(data["description"]) if data.get("description") else None

        return cls(
            name=name,
            patterns=tuple(patterns),
            require_sid=require_sid,
            required_sids=required_sids,
            sid_paths=sid_paths,
            description=description,
        )


@dataclass(slots=True)
class SidCheckResult:
    """Outcome of the SID check."""

    base: str | None
    head: str
    changed_files: Sequence[str]
    changed_sids: Sequence[str]
    sid_files: Sequence[str]
    triggered_watchlist: Sequence[dict[str, object]]
    failures: Sequence[str]

    @property
    def ok(self) -> bool:
        return not self.failures


def normalise_sid(value: str) -> str:
    match = SID_PATTERN.search(value)
    if not match:
        raise ValueError(f"Unsupported SID format: {value!r}")
    digits = match.group(1)
    return f"SID-{digits}"


def run_git_command(args: Sequence[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise SidCheckError(
            "git command failed: "
            + " ".join(args)
            + f"\n{result.stderr.strip()}"
        )
    return result.stdout


def ref_exists(ref: str) -> bool:
    try:
        run_git_command(["rev-parse", "--verify", f"{ref}^{{commit}}"])
    except SidCheckError:
        return False
    return True


def determine_base_revision(user_base: str | None, head: str) -> str | None:
    if user_base:
        return user_base

    env_candidates = [
        ("GITHUB_BASE_SHA", None),
        ("PR_BASE_SHA", None),
        ("CI_MERGE_REQUEST_TARGET_BRANCH_SHA", None),
        ("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "origin/{value}"),
        ("GITHUB_BASE_REF", "origin/{value}"),
    ]

    for env, template in env_candidates:
        value = os.getenv(env)
        if not value:
            continue
        candidate = template.format(value=value) if template else value
        if ref_exists(candidate):
            return candidate

    for candidate in ("origin/main", "origin/master", "main", "master"):
        if ref_exists(candidate):
            return candidate

    if ref_exists(head):
        return head

    return None


def gather_changed_files(
    base: str | None,
    head: str,
    staged: bool,
    include_worktree: bool,
) -> list[str]:
    args = ["diff"]
    if staged:
        args.append("--staged")

    args.extend(["--name-only", "--diff-filter=ACMR"])

    if not staged:
        if include_worktree:
            if base:
                args.append(base)
        else:
            if base and head:
                args.extend([base, head])
            elif base:
                args.append(base)
            elif head:
                args.append(head)

    output = run_git_command(args)
    return [line.strip() for line in output.splitlines() if line.strip()]


def gather_diff(base: str | None, head: str, staged: bool, include_worktree: bool) -> str:
    args = ["diff"]
    if staged:
        args.append("--staged")

    args.append("--unified=0")

    if not staged:
        if include_worktree:
            if base:
                args.append(base)
        else:
            if base and head:
                args.extend([base, head])
            elif base:
                args.append(base)
            elif head:
                args.append(head)

    return run_git_command(args)


def extract_sids_from_diff(diff_text: str) -> set[str]:
    sids: set[str] = set()
    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for match in SID_PATTERN.finditer(line):
            sids.add(f"SID-{match.group(1)}")
    return sids


def detect_sid_files(changed_files: Iterable[str]) -> list[str]:
    sid_related: list[str] = []
    for path in changed_files:
        lower_path = path.lower()
        if "sid" in lower_path or lower_path.startswith("docs/security/"):
            sid_related.append(path)
    return sid_related


def load_watchlist(path: Path) -> list[WatchlistEntry]:
    if not path.exists():
        return []

    data = yaml.safe_load(path.read_text())
    if data is None:
        return []

    if isinstance(data, dict):
        entries_data = data.get("entries") or data.get("watchlist") or []
    elif isinstance(data, list):
        entries_data = data
    else:
        raise SidCheckError(
            f"Unsupported watchlist structure in {path}. Expected list or mapping."
        )

    entries: list[WatchlistEntry] = []
    for item in entries_data:
        if not isinstance(item, dict):
            raise SidCheckError(
                f"Watchlist entry must be a mapping, got {type(item)!r}: {item!r}"
            )
        try:
            entries.append(WatchlistEntry.from_mapping(item))
        except ValueError as exc:
            raise SidCheckError(f"Invalid watchlist entry in {path}: {exc}") from exc
    return entries


def evaluate_watchlist(
    entries: Sequence[WatchlistEntry],
    changed_files: Sequence[str],
    changed_sids: set[str],
    sid_files: Sequence[str],
) -> tuple[list[dict[str, object]], list[str]]:
    triggered: list[dict[str, object]] = []
    failures: list[str] = []

    for entry in entries:
        matched_paths = [
            path for path in changed_files if any(fnmatch(path, pattern) for pattern in entry.patterns)
        ]
        if not matched_paths:
            continue

        info: dict[str, object] = {
            "name": entry.name,
            "description": entry.description,
            "patterns": list(entry.patterns),
            "matched_paths": matched_paths,
            "required_sids": sorted(entry.required_sids),
            "sid_paths": list(entry.sid_paths),
        }

        requirement_failures: list[str] = []

        if entry.required_sids:
            intersection = sorted(changed_sids & entry.required_sids)
            info["matched_sids"] = intersection
            if not intersection:
                requirement_failures.append(
                    "none of the required SIDs were updated"
                )
        elif entry.sid_paths:
            sid_path_matches = [
                path for path in sid_files if any(fnmatch(path, pattern) for pattern in entry.sid_paths)
            ]
            info["matched_sid_paths"] = sid_path_matches
            if not sid_path_matches:
                requirement_failures.append(
                    "no SID files matching the configured sid_paths were touched"
                )
        elif entry.require_sid:
            if not changed_sids and not sid_files:
                requirement_failures.append("no SID updates detected")

        if requirement_failures:
            failures.append(
                f"Watchlist '{entry.name}' triggered by {matched_paths} but {', '.join(requirement_failures)}."
            )
            info["status"] = "failed"
            info["errors"] = requirement_failures
        else:
            info["status"] = "ok"

        triggered.append(info)

    return triggered, failures


def create_result(
    base: str | None,
    head: str,
    changed_files: list[str],
    changed_sids: set[str],
    sid_files: list[str],
    triggered: list[dict[str, object]],
    failures: list[str],
) -> SidCheckResult:
    return SidCheckResult(
        base=base,
        head=head,
        changed_files=tuple(changed_files),
        changed_sids=tuple(sorted(changed_sids)),
        sid_files=tuple(sorted(sid_files)),
        triggered_watchlist=tuple(triggered),
        failures=tuple(failures),
    )


def format_text(result: SidCheckResult) -> str:
    lines = [
        "Security Incident Document (SID) check",
        f"  Base: {result.base or '(none)'}",
        f"  Head: {result.head}",
        f"  Changed files: {len(result.changed_files)}",
        f"  Detected SIDs: {', '.join(result.changed_sids) if result.changed_sids else 'none'}",
        f"  SID-related files: {len(result.sid_files)}",
    ]

    if result.triggered_watchlist:
        lines.append("  Watchlist entries triggered:")
        for entry in result.triggered_watchlist:
            name = entry.get("name", "(unknown)")
            status = entry.get("status")
            lines.append(f"    - {name} [{status}]")
            matched_paths = entry.get("matched_paths") or []
            if matched_paths:
                lines.append(f"      Paths: {', '.join(matched_paths)}")
            matched_sids = entry.get("matched_sids") or []
            if matched_sids:
                lines.append(f"      SIDs: {', '.join(matched_sids)}")
            matched_sid_paths = entry.get("matched_sid_paths") or []
            if matched_sid_paths:
                lines.append(f"      SID files: {', '.join(matched_sid_paths)}")
            errors = entry.get("errors") or []
            if errors:
                for error in errors:
                    lines.append(f"      ! {error}")
    else:
        lines.append("  Watchlist entries triggered: none")

    if result.failures:
        lines.append("")
        lines.append("Failures:")
        for failure in result.failures:
            lines.append(f"  - {failure}")

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate SID updates against the watchlist")
    parser.add_argument("--base", help="Base revision to diff against")
    parser.add_argument("--head", default="HEAD", help="Head revision to diff (default: HEAD)")
    parser.add_argument("--watchlist", default=str(DEFAULT_WATCHLIST_PATH), help="Path to the SID watchlist YAML")
    parser.add_argument("--staged", action="store_true", help="Compare staged changes instead of commits")
    parser.add_argument(
        "--no-worktree",
        action="store_true",
        help="Diff commits only (exclude local working tree changes)",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    args = parser.parse_args(argv)

    head = args.head
    base = determine_base_revision(args.base, head)

    include_worktree = not args.no_worktree and not args.staged and head.upper() == "HEAD"

    try:
        changed_files = gather_changed_files(base, head, args.staged, include_worktree)
        diff_text = gather_diff(base, head, args.staged, include_worktree)
    except SidCheckError as error:
        print(error, file=sys.stderr)
        return 2

    changed_sids = extract_sids_from_diff(diff_text)
    sid_files = detect_sid_files(changed_files)

    try:
        watchlist_entries = load_watchlist(Path(args.watchlist))
    except SidCheckError as error:
        print(error, file=sys.stderr)
        return 2

    triggered, failures = evaluate_watchlist(
        watchlist_entries,
        changed_files,
        changed_sids,
        sid_files,
    )

    result = create_result(base, head, changed_files, changed_sids, sid_files, triggered, failures)

    if args.format == "json":
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
    else:
        print(format_text(result))

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
