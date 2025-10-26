"""Run only the pytest tests impacted by recent code changes."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence


def get_changed_files(since: str) -> List[str]:
    """Return a list of file paths changed since the provided Git revision."""

    result = subprocess.run(
        ["git", "diff", "--name-only", since],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def map_files_to_tests(changed_files: Sequence[str]) -> List[str]:
    """Map source files to the pytest tests that should be executed."""

    test_files: set[str] = set()
    for file_path in changed_files:
        path = Path(file_path)
        if "tests" in path.parts and path.suffix == ".py":
            test_files.add(str(path))
            continue

        if path.suffix != ".py":
            continue

        if path.parts and path.parts[0] in {"theo", "mcp_server"}:
            stem = path.stem
            patterns = [
                f"tests/**/*test*{stem}*.py",
                f"tests/**/*{stem}*test*.py",
            ]
            for pattern in patterns:
                for match in Path(".").glob(pattern):
                    test_files.add(str(match))
    return sorted(test_files)


def run_pytest(selected_tests: Iterable[str]) -> int:
    """Execute pytest with the selected tests."""

    tests = list(selected_tests)
    if not tests:
        print("No impacted tests detected; running fast suite instead.")
        tests = ["tests/unit", "tests/domain", "tests/utils"]
    command = ["pytest", *tests]
    return subprocess.call(command)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since",
        default="HEAD~1",
        help="Git revision to diff against when determining impacted tests.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    changed_files = get_changed_files(args.since)
    selected_tests = map_files_to_tests(changed_files)
    return run_pytest(selected_tests)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
