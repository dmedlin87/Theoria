"""Utilities for detecting regressions in pytest execution times."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


def save_baseline(destination: Path, results: Dict[str, float]) -> Path:
    """Persist the baseline metrics to ``destination``."""

    destination.write_text(json.dumps(results, indent=2, sort_keys=True))
    return destination


def load_baseline(source: Path) -> Dict[str, float]:
    """Load an existing baseline file, returning an empty mapping if missing."""

    if not source.exists():
        return {}
    try:
        return json.loads(source.read_text())
    except json.JSONDecodeError:
        return {}


def detect_performance_regressions(
    baseline_file: Path, current_results: Dict[str, float]
) -> Dict[str, object]:
    """Detect regressions between baseline metrics and ``current_results``."""

    if not baseline_file.exists():
        save_baseline(baseline_file, current_results)
        return {"status": "baseline_created", "regressions": []}

    baseline = load_baseline(baseline_file)
    regressions: List[Dict[str, object]] = []
    improvements = 0

    for test_name, current_time in current_results.items():
        baseline_time = baseline.get(test_name)
        if baseline_time is None:
            continue

        if baseline_time == 0:
            continue

        change_ratio = current_time / baseline_time
        if change_ratio > 1.3:
            regressions.append(
                {
                    "test": test_name,
                    "baseline": baseline_time,
                    "current": current_time,
                    "regression_percent": ((current_time - baseline_time) / baseline_time)
                    * 100,
                }
            )
        elif change_ratio < 0.9:
            improvements += 1

    return {
        "status": "analysis_complete",
        "regressions": regressions,
        "improvement_count": improvements,
    }


if __name__ == "__main__":
    baseline_path = Path("perf_metrics/test_duration_baseline.json")
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    current = {"example::test_case": 1.0}
    print(detect_performance_regressions(baseline_path, current))
