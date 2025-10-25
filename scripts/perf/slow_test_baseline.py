#!/usr/bin/env python3
"""Collect and rerun the slowest pytest cases to build a stability baseline."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence

DURATIONS_REGEX = re.compile(
    r"^\s*([0-9]*\.?[0-9]+)s\s+(call|setup|teardown)\s+(?P<nodeid>\S+)"
)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect the slowest pytest tests and rerun them multiple times to"
            " establish a flake-rate baseline."
        )
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=20,
        help="How many times to rerun each slow test (default: 20).",
    )
    parser.add_argument(
        "--output-dir",
        default="logs/test-baseline",
        help="Directory root for rerun artifacts (default: logs/test-baseline).",
    )
    parser.add_argument(
        "--pytest-args",
        default="",
        help=(
            "Extra arguments to forward to pytest for the initial discovery run "
            "and each rerun. Provide as a single quoted string."
        ),
    )
    parser.add_argument(
        "tests",
        nargs="*",
        help=(
            "Optional explicit list of pytest nodeids to baseline. If omitted, "
            "the slowest tests from the durations report are used."
        ),
    )
    return parser.parse_args(argv)


def run_command(cmd: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def _utcnow() -> datetime:
    """Return a timezone-aware timestamp for consistent artifact naming."""

    return datetime.now(timezone.utc)


def ensure_output_dir(base_dir: Path) -> Path:
    timestamp = _utcnow().strftime("%Y%m%d-%H%M%S")
    run_dir = base_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def extract_slowest_tests(output: str) -> List[str]:
    tests: List[str] = []
    seen = set()
    for line in output.splitlines():
        match = DURATIONS_REGEX.search(line)
        if not match:
            continue
        nodeid = match.group("nodeid")
        if nodeid not in seen:
            seen.add(nodeid)
            tests.append(nodeid)
    return tests


def sanitize_nodeid(nodeid: str) -> str:
    sanitized = nodeid.replace(os.sep, "__").replace("::", "__")
    sanitized = sanitized.replace("/", "__").replace("\\", "__")
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", sanitized)
    return sanitized


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def build_pytest_command(
    nodeid: str | None,
    junit_path: Path | None,
    extra_args: Iterable[str],
) -> List[str]:
    cmd: List[str] = ["pytest"]
    if nodeid:
        cmd.append(nodeid)
    cmd.extend(["--durations=50", "--durations-min=0.05"] if nodeid is None else [])
    if junit_path is not None:
        cmd.extend(["--junitxml", str(junit_path)])
    cmd.extend(extra_args)
    return cmd


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)

    extra_args: List[str] = shlex.split(args.pytest_args)
    base_dir = Path(args.output_dir)
    run_dir = ensure_output_dir(base_dir)

    summary: dict = {
        "generated_at": _utcnow().isoformat().replace("+00:00", "Z"),
        "repeat": args.repeat,
        "pytest_args": extra_args,
        "runs": [],
    }

    slow_tests: List[str]
    if args.tests:
        slow_tests = list(args.tests)
        discovery_stdout = "\n".join(args.tests)
        discovery_stderr = ""
        discovery_returncode = 0
    else:
        discovery_cmd = build_pytest_command(None, None, extra_args)
        discovery_result = run_command(discovery_cmd)

        discovery_log = textwrap.dedent(
            f"""\
            === pytest durations discovery ===\n\
            command: {' '.join(discovery_cmd)}\n\
            returncode: {discovery_result.returncode}\n\
            --- stdout ---\n\
            {discovery_result.stdout}\n\
            --- stderr ---\n\
            {discovery_result.stderr}\n\
            """
        )
        write_text(run_dir / "durations.log", discovery_log)

        if discovery_result.returncode != 0:
            print("Pytest durations command failed; see durations.log for details", file=sys.stderr)
            return discovery_result.returncode

        slow_tests = extract_slowest_tests(discovery_result.stdout)
        discovery_stdout = discovery_result.stdout
        discovery_stderr = discovery_result.stderr
        discovery_returncode = discovery_result.returncode

    summary.update(
        {
            "discovery": {
                "returncode": discovery_returncode,
                "stdout": discovery_stdout,
                "stderr": discovery_stderr,
            },
            "tests": slow_tests,
        }
    )

    if not slow_tests:
        print("No slow tests were detected; nothing to rerun.")
        write_text(run_dir / "summary.json", json.dumps(summary, indent=2))
        return 0

    failures = []
    for nodeid in slow_tests:
        test_dir = run_dir / sanitize_nodeid(nodeid)
        test_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== Rerunning {nodeid} ({args.repeat} iterations) ===")
        for iteration in range(1, args.repeat + 1):
            junit_path = test_dir / f"run_{iteration:02d}.xml"
            rerun_cmd = ["pytest", nodeid, "--junitxml", str(junit_path), *extra_args]
            start = time.perf_counter()
            result = run_command(rerun_cmd)
            duration = time.perf_counter() - start

            json_payload = {
                "test": nodeid,
                "iteration": iteration,
                "returncode": result.returncode,
                "duration_seconds": duration,
                "command": rerun_cmd,
            }
            if result.stdout:
                json_payload["stdout"] = result.stdout
            if result.stderr:
                json_payload["stderr"] = result.stderr
            write_text(test_dir / f"run_{iteration:02d}.json", json.dumps(json_payload, indent=2))

            summary["runs"].append(
                {
                    "test": nodeid,
                    "iteration": iteration,
                    "returncode": result.returncode,
                    "duration_seconds": duration,
                    "junit_xml": str(junit_path.relative_to(run_dir)),
                }
            )

            if result.returncode != 0:
                failures.append({
                    "test": nodeid,
                    "iteration": iteration,
                    "returncode": result.returncode,
                })

    write_text(run_dir / "summary.json", json.dumps(summary, indent=2))

    if failures:
        print("\nDetected failures during reruns:")
        for failure in failures:
            print(
                f" - {failure['test']} iteration {failure['iteration']} failed with return code {failure['returncode']}"
            )
        print(f"Artifacts written to: {run_dir}")
        return 1

    print(f"All reruns passed. Artifacts written to: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
