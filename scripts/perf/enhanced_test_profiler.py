"""Collect and persist fine-grained pytest performance metrics."""

from __future__ import annotations

import contextlib
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterator, List

try:  # pragma: no cover - psutil optional in lightweight environments
    import psutil
except ModuleNotFoundError:  # pragma: no cover - fallback when psutil missing
    psutil = None


@dataclass
class TestMetrics:
    """Container for capturing detailed information about a single test run."""

    name: str
    duration: float
    memory_peak: int
    setup_time: float
    teardown_time: float
    fixture_count: int


class TestProfiler:
    """Profile pytest executions and provide optimisation suggestions."""

    def __init__(self) -> None:
        self.metrics: Dict[str, TestMetrics] = {}

    @contextlib.contextmanager
    def profile_test(self, nodeid: str, *, fixture_count: int = 0) -> Iterator[None]:
        """Context manager for profiling an individual test execution."""

        start = time.perf_counter()
        start_memory = self._current_memory()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            end_memory = self._current_memory()
            memory_peak = max(end_memory - start_memory, 0)
            self.metrics[nodeid] = TestMetrics(
                name=nodeid,
                duration=duration,
                memory_peak=memory_peak,
                setup_time=0.0,
                teardown_time=0.0,
                fixture_count=fixture_count,
            )

    def record_metrics(
        self,
        nodeid: str,
        *,
        duration: float,
        memory_peak: int,
        setup_time: float,
        teardown_time: float,
        fixture_count: int,
    ) -> None:
        """Record metrics collected externally (e.g. from pytest hooks)."""

        self.metrics[nodeid] = TestMetrics(
            name=nodeid,
            duration=duration,
            memory_peak=memory_peak,
            setup_time=setup_time,
            teardown_time=teardown_time,
            fixture_count=fixture_count,
        )

    def generate_optimization_report(self) -> Dict[str, object]:
        """Summarise the collected metrics and provide optimisation hints."""

        if not self.metrics:
            return {"summary": {"total_tests": 0, "avg_duration": 0.0}}

        slow_tests = sorted(
            self.metrics.values(), key=lambda metric: metric.duration, reverse=True
        )[:20]

        return {
            "slowest_tests": [
                {
                    "name": metric.name,
                    "duration": metric.duration,
                    "memory_peak": metric.memory_peak,
                    "suggestions": self._suggest_optimizations(metric),
                }
                for metric in slow_tests
            ],
            "summary": {
                "total_tests": len(self.metrics),
                "avg_duration": sum(m.duration for m in self.metrics.values())
                / len(self.metrics),
                "memory_intensive_tests": [
                    metric.name
                    for metric in self.metrics.values()
                    if metric.memory_peak > 100_000_000
                ],
            },
        }

    def write_report(self, destination: Path) -> Path:
        """Write the optimisation report to ``destination`` as JSON."""

        report = self.generate_optimization_report()
        destination.write_text(json.dumps(report, indent=2, sort_keys=True))
        return destination

    def _current_memory(self) -> int:
        if psutil is None:
            return 0
        return psutil.Process().memory_info().rss

    def _suggest_optimizations(self, metric: TestMetrics) -> List[str]:
        suggestions: List[str] = []
        if metric.duration > 1.5:
            suggestions.append("consider marking as slow or refactoring fixtures")
        if metric.memory_peak > 150_000_000:
            suggestions.append("investigate large fixture payloads or object lifetimes")
        if metric.fixture_count > 10:
            suggestions.append("reduce fixture fan-out or collapse redundant layers")
        if not suggestions:
            suggestions.append("no immediate action required")
        return suggestions


if __name__ == "__main__":
    profiler = TestProfiler()
    report_path = Path("perf_metrics/test_profile_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    profiler.write_report(report_path)
    print(json.dumps(asdict(TestMetrics("example::test_case", 0.1, 0, 0.0, 0.0, 1))))
    print(report_path)
