#!/usr/bin/env python3
"""Collect runtime profiles for heavy pytest marker suites.

This utility executes pytest for each opt-in marker (``schema``, ``pgvector``,
``contract``) and records both wall-clock timings and the slowest individual
tests that were reported by ``--durations``. The resulting JSON file can be
committed to ``perf_metrics/pytest_marker_baselines.json`` to track historical
changes and feed CI monitoring.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "perf_metrics" / "pytest_marker_baselines.json"

_SLOW_TEST_RE = re.compile(
    r"^(?P<duration>[0-9]+\.[0-9]+)s\s+"  # duration in seconds
    r"(?P<phase>call|setup|teardown)\s+"   # pytest phase
    r"(?P<nodeid>.+)$"                      # test node id
)


@dataclass
class SlowTestRecord:
    nodeid: str
    duration: float
    phase: str

    def as_dict(self) -> dict[str, object]:
        return {"nodeid": self.nodeid, "duration": self.duration, "phase": self.phase}


@dataclass
class MarkerProfile:
    marker: str
    command: list[str]
    wall_time: float
    slow_tests: list[SlowTestRecord]

    def as_dict(self) -> dict[str, object]:
        return {
            "marker": self.marker,
            "command": self.command,
            "wall_time_seconds": round(self.wall_time, 3),
            "slow_tests": [record.as_dict() for record in self.slow_tests],
        }


def _build_command(marker: str) -> list[str]:
    base = ["pytest", f"-m", marker, "--durations=25", "--durations-min=0.05", "-q"]
    if marker == "schema":
        base.insert(1, "--schema")
    elif marker == "pgvector":
        base.insert(1, "--schema")
        base.insert(1, "--pgvector")
    elif marker == "contract":
        base.insert(1, "--contract")
    return base


def _parse_slowest(lines: Iterable[str]) -> list[SlowTestRecord]:
    records: list[SlowTestRecord] = []
    capture = False
    for line in lines:
        clean = line.strip()
        if clean.startswith("slowest durations"):
            capture = True
            continue
        if capture:
            if not clean:
                continue
            match = _SLOW_TEST_RE.match(clean)
            if match:
                records.append(
                    SlowTestRecord(
                        nodeid=match.group("nodeid"),
                        duration=float(match.group("duration")),
                        phase=match.group("phase"),
                    )
                )
    return records


def _run_profile(marker: str) -> MarkerProfile:
    command = _build_command(marker)
    start = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    output_lines: list[str] = []
    assert process.stdout is not None  # for type checkers; stdout is PIPE
    try:
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            output_lines.append(line.rstrip("\n"))
    finally:
        process.stdout.close()

    returncode = process.wait()
    end = time.perf_counter()

    if returncode != 0:
        raise SystemExit(
            f"pytest exited with status {returncode} while profiling marker '{marker}'"
        )

    slow_tests = _parse_slowest(output_lines)
    return MarkerProfile(marker, command, end - start, slow_tests)


def profile_markers(markers: Iterable[str]) -> dict[str, MarkerProfile]:
    results: dict[str, MarkerProfile] = {}
    for marker in markers:
        results[marker] = _run_profile(marker)
    return results


def _build_payload(profiles: dict[str, MarkerProfile]) -> dict[str, object]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profiles": {marker: profile.as_dict() for marker, profile in profiles.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Profile pytest marker suites")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination JSON file for captured durations.",
    )
    parser.add_argument(
        "markers",
        nargs="*",
        default=["schema", "pgvector", "contract"],
        help="Markers to profile (defaults to schema, pgvector, contract).",
    )
    args = parser.parse_args(argv)

    profiles = profile_markers(args.markers)
    payload = _build_payload(profiles)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote marker profiles to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
