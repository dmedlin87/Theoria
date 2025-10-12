#!/usr/bin/env python3
"""Run Trufflehog against the repository and compare with the baseline."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Tuple

DEFAULT_BASELINE = Path("docs/security/trufflehog-baseline.json")


def load_findings(stdout: str) -> list[dict]:
    findings: list[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            findings.append(json.loads(line))
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Unable to parse trufflehog output line: {line[:80]}...") from exc
    return findings


def fingerprint(entry: dict) -> Tuple[str, str, str]:
    strings = entry.get("stringsFound") or []
    candidate = strings[0] if strings else ""
    return (
        entry.get("path", ""),
        candidate.strip(),
        entry.get("reason", ""),
    )


def run_trufflehog() -> subprocess.CompletedProcess[str]:
    """Execute the legacy CLI bundled with `pip install trufflehog`."""

    cmd = [
        "trufflehog",
        "--json",
        "--regex",
        "--entropy=False",
        "--repo_path",
        ".",
        "file://.",
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Path to the JSON baseline allow-list.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to store the raw trufflehog findings JSON.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Append any new findings to the baseline after manual review.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_trufflehog()
    findings = load_findings(result.stdout)

    if args.output:
        args.output.write_text(json.dumps(findings, indent=2))

    baseline_entries: list[dict] = []
    if args.baseline.exists():
        baseline_entries = json.loads(args.baseline.read_text())

    baseline_fingerprints = {fingerprint(entry) for entry in baseline_entries}
    new_findings = [entry for entry in findings if fingerprint(entry) not in baseline_fingerprints]

    print(f"Trufflehog return code: {result.returncode}")
    print(f"Total findings: {len(findings)}")
    print(f"Baseline findings: {len(baseline_entries)}")
    print(f"New findings: {len(new_findings)}")

    if new_findings:
        print(json.dumps(new_findings, indent=2))
        if args.update_baseline:
            baseline_entries.extend(new_findings)
            args.baseline.write_text(json.dumps(baseline_entries, indent=2) + "\n")
            print(f"Baseline updated: {args.baseline}")
            return 0
        print("New secrets detected. Investigate before updating the baseline.")
        return 1

    if args.update_baseline:
        print("No new findings; baseline left unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
