"""Aggregate backend and frontend coverage data and compare to policy baselines."""
from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict

DEFAULT_BASELINE = Path("metrics/coverage-baseline.json")
DEFAULT_FRONTEND_DIR = Path("theo/services/web/coverage")
DEFAULT_OUTPUT = Path("coverage-report.json")


class CoverageError(RuntimeError):
    """Raised when coverage artifacts are missing or malformed."""


def _load_backend_metrics(report_path: Path) -> dict[str, Any]:
    if not report_path.exists():
        raise CoverageError(f"Backend coverage report '{report_path}' not found.")
    tree = ET.parse(report_path)
    root = tree.getroot()
    try:
        line_rate = float(root.attrib["line-rate"])
        lines_valid = int(root.attrib["lines-valid"])
        lines_covered = int(root.attrib["lines-covered"])
    except KeyError as exc:  # pragma: no cover - defensive
        raise CoverageError(f"Coverage XML missing attribute: {exc}") from exc
    return {
        "line_rate": line_rate,
        "lines_valid": lines_valid,
        "lines_covered": lines_covered,
    }


def _load_frontend_metrics(coverage_dir: Path) -> dict[str, Any]:
    summary_path = coverage_dir / "coverage-summary.json"
    if not summary_path.exists():
        raise CoverageError(f"Vitest coverage summary '{summary_path}' not found.")
    data = json.loads(summary_path.read_text())
    totals = data.get("total")
    if not isinstance(totals, dict):
        raise CoverageError("Vitest coverage summary missing 'total' section.")

    def _percent(metric: Dict[str, Any]) -> float:
        if not isinstance(metric, dict):
            return 0.0
        if isinstance(metric.get("pct"), (int, float)):
            return float(metric["pct"]) / 100
        covered = metric.get("covered")
        total = metric.get("total")
        if isinstance(covered, (int, float)) and isinstance(total, (int, float)) and total:
            return float(covered) / float(total)
        return 0.0

    metrics = {name: _percent(value) for name, value in totals.items()}
    return metrics


def _load_baseline(baseline_path: Path) -> dict[str, Any]:
    if not baseline_path.exists():
        raise CoverageError(f"Baseline coverage policy '{baseline_path}' not found.")
    return json.loads(baseline_path.read_text())


def _format_delta(actual: float, expected: float) -> str:
    delta = (actual - expected) * 100
    return f"{delta:+.2f}%"


def aggregate(
    backend_path: Path,
    frontend_dir: Path,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[str]]:
    backend = _load_backend_metrics(backend_path)
    frontend = _load_frontend_metrics(frontend_dir)
    baseline = _load_baseline(baseline_path)

    deficits: list[str] = []

    backend_target = float(baseline.get("backend", {}).get("line_rate", 0.0))
    if backend["line_rate"] < backend_target:
        deficits.append(
            "Backend coverage "
            f"{backend['line_rate']*100:.2f}% below baseline {backend_target*100:.2f}%"
        )

    frontend_targets = baseline.get("frontend", {})
    for metric, threshold in frontend_targets.items():
        actual = frontend.get(metric, 0.0)
        if actual < threshold:
            deficits.append(
                f"Frontend {metric} coverage {actual*100:.2f}% below baseline {threshold*100:.2f}%"
            )

    return {
        "backend": backend,
        "frontend": frontend,
        "baseline": baseline,
    }, deficits


def write_outputs(summary: dict[str, Any], output_path: Path) -> None:
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


def emit_github_outputs(summary: dict[str, Any], deficits: list[str]) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        return
    lines: list[str] = []
    lines.append(f"regressed={'true' if deficits else 'false'}")

    backend = summary["backend"]
    baseline_backend = summary["baseline"].get("backend", {}).get("line_rate", 0.0)
    frontend = summary["frontend"]
    frontend_targets = summary["baseline"].get("frontend", {})

    report_lines = [
        "Coverage monitor summary:",
        f"- Backend lines: {backend['line_rate']*100:.2f}% (baseline {baseline_backend*100:.2f}%, "
        f"Δ {_format_delta(backend['line_rate'], baseline_backend)})",
    ]

    for metric, threshold in frontend_targets.items():
        actual = frontend.get(metric, 0.0)
        report_lines.append(
            f"- Frontend {metric}: {actual*100:.2f}% (baseline {threshold*100:.2f}%, "
            f"Δ {_format_delta(actual, threshold)})"
        )

    if deficits:
        report_lines.append("- Regressions detected:")
        report_lines.extend(f"  * {item}" for item in deficits)

    lines.append("summary<<'EOF'")
    lines.extend(report_lines)
    lines.append("EOF")

    with open(github_output, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend-report",
        type=Path,
        default=Path("coverage.xml"),
        help="Path to the backend coverage XML report.",
    )
    parser.add_argument(
        "--frontend-coverage",
        type=Path,
        default=DEFAULT_FRONTEND_DIR,
        help="Directory containing Vitest coverage artifacts.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Coverage baseline policy JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="File to write the aggregated coverage summary JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary, deficits = aggregate(args.backend_report, args.frontend_coverage, args.baseline)
    except CoverageError as error:
        print(str(error), file=sys.stderr)
        return 1

    write_outputs(summary, args.output)
    emit_github_outputs(summary, deficits)

    print("Coverage aggregation complete.")
    if deficits:
        print("Regressions detected:")
        for item in deficits:
            print(f" - {item}")
    else:
        print("No regressions against baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
