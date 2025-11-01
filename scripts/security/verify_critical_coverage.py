"""Validate coverage thresholds for critical packages."""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

THRESHOLDS = {
    "theo.services.api.app.core": 0.90,
    "theo.domain": 0.90,
    "theo.application": 0.90,
    "theo.services.api.app.ingest": 0.90,
    "theo.services.api.app.retriever": 0.90,
    "theo.services.api.app.ai.rag": 0.90,
}


def _extract_line_rate(package: ET.Element) -> float:
    line_rate = package.attrib.get("line-rate")
    if line_rate is None:
        return 0.0
    try:
        return float(line_rate)
    except ValueError:  # pragma: no cover - defensive guard
        return 0.0


def _normalize(name: str) -> str:
    return name.replace("/", ".")


def evaluate_coverage(report_path: Path) -> list[str]:
    tree = ET.parse(report_path)
    root = tree.getroot()

    package_nodes = root.findall(".//package")
    deficits: list[str] = []
    for package in package_nodes:
        normalized = _normalize(package.attrib.get("name", ""))
        for target, threshold in THRESHOLDS.items():
            if normalized.startswith(target):
                rate = _extract_line_rate(package)
                if rate < threshold:
                    deficits.append(
                        f"Package '{normalized}' coverage {rate:.2%} below threshold {threshold:.0%}"
                    )
    missing_targets = [t for t in THRESHOLDS if not any(_normalize(pkg.attrib.get("name", "")).startswith(t) for pkg in package_nodes)]
    for missing in missing_targets:
        deficits.append(f"Coverage report missing target package '{missing}'")
    return deficits


def main() -> int:
    report_path = Path("coverage.xml")
    if not report_path.exists():
        print("coverage.xml not found; run pytest with --cov before invoking", file=sys.stderr)
        return 1
    failures = evaluate_coverage(report_path)
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Critical coverage thresholds satisfied.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
