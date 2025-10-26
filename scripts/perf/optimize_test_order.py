"""Helper utilities for reasoning about optimal pytest execution order."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


FAST_PATTERNS = [
    "tests/unit/",
    "tests/domain/",
    "tests/utils/",
]

MEDIUM_PATTERNS = [
    "tests/application/",
    "tests/adapters/",
]

SLOW_PATTERNS = [
    "tests/api/",
    "tests/db/",
    "tests/services/",
]


def analyze_test_dependencies() -> Dict[str, List[str]]:
    """Return groupings that can be used to prioritise pytest execution order."""

    return {
        "fast": FAST_PATTERNS.copy(),
        "medium": MEDIUM_PATTERNS.copy(),
        "slow": SLOW_PATTERNS.copy(),
    }


def generate_plan_file(destination: Path) -> Path:
    """Persist the recommended ordering to ``destination`` in JSON format."""

    plan = analyze_test_dependencies()
    destination.write_text(json.dumps(plan, indent=2, sort_keys=True))
    return destination


if __name__ == "__main__":
    plan_path = Path("perf_metrics/test_ordering_plan.json")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    generate_plan_file(plan_path)
    print(plan_path)
