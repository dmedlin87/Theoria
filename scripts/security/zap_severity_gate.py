#!/usr/bin/env python3
"""Fail a build when OWASP ZAP alerts meet or exceed a severity threshold."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable

SEVERITY_ORDER = ["informational", "low", "medium", "high", "very high"]


def _normalise(value: str | None) -> str:
    return (value or "").strip().lower()


def _alert_severity(alert: Dict[str, object]) -> str:
    for key in ("risk", "riskdesc", "alert", "name"):
        severity = _normalise(str(alert.get(key, "")))
        if severity:
            if "very high" in severity:
                return "very high"
            if "high" in severity:
                return "high"
            if "medium" in severity:
                return "medium"
            if "low" in severity:
                return "low"
    return "informational"


def _count_alerts(alerts: Iterable[Dict[str, object]]) -> Dict[str, int]:
    counts = {level: 0 for level in SEVERITY_ORDER}
    for alert in alerts:
        level = _alert_severity(alert)
        counts[level] = counts.get(level, 0) + 1
    return counts


def _iter_alerts(data: Dict[str, object]) -> Iterable[Dict[str, object]]:
    for site in data.get("site", []):
        for alert in site.get("alerts", []):
            yield alert


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to zap-baseline JSON report produced with -J")
    parser.add_argument(
        "--fail-on",
        choices=SEVERITY_ORDER,
        default="high",
        help="Lowest severity that should fail the build (default: high)",
    )
    args = parser.parse_args(argv)

    data = json.loads(args.report.read_text())
    alerts = list(_iter_alerts(data))
    counts = _count_alerts(alerts)

    severity_index = SEVERITY_ORDER.index(args.fail_on)
    breach_levels = [level for level in SEVERITY_ORDER[severity_index:] if counts.get(level, 0)]

    for level in SEVERITY_ORDER:
        total = counts.get(level, 0)
        print(f"{level.title():<14}: {total}")

    if breach_levels:
        highest = breach_levels[-1]
        print(
            f"::error::ZAP detected {counts[highest]} {highest} severity alert(s); gating merge until addressed.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
