"""Determine which rag_eval modules need to run for the current diff."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git_diff_range() -> list[str]:
    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref:
        diff_range = f"origin/{base_ref}...HEAD"
    else:
        diff_range = "HEAD^...HEAD"
    try:
        output = subprocess.check_output(
            ["git", "diff", "--name-only", diff_range], cwd=REPO_ROOT
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - fallback path
        sys.stderr.write(f"Failed to compute git diff ({exc}); defaulting to HEAD^...HEAD\n")
        output = subprocess.check_output(["git", "diff", "--name-only", "HEAD^...HEAD"], cwd=REPO_ROOT)
    return [line.strip() for line in output.decode().splitlines() if line.strip()]


def _module_from_path(path: str) -> str | None:
    if path.startswith("theo/services/"):
        parts = path.split("/")
        if len(parts) >= 4:
            return "/".join(parts[:4])
        return parts[2] if len(parts) > 2 else "theo/services"
    if path.startswith("theo/search/"):
        return "theo/search"
    if path.startswith("tests/cli/"):
        return "cli"
    if path.startswith("data/eval/"):
        return "data-eval"
    if path.startswith("scripts/perf/"):
        return "scripts/perf"
    return None


def determine_modules(paths: Iterable[str]) -> list[str]:
    modules = {module for path in paths if (module := _module_from_path(path))}
    if not modules:
        return ["global"]
    return sorted(modules)


def main() -> None:
    modules = determine_modules(_git_diff_range())
    sys.stdout.write(" ".join(modules))


if __name__ == "__main__":
    main()
