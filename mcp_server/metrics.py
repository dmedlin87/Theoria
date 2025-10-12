"""Metrics collection and exposure for MCP server."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict

LOGGER = logging.getLogger(__name__)


@dataclass
class ToolMetrics:
    """Metrics for a single tool."""

    invocation_count: int = 0
    error_count: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    last_invoked: float | None = None

    def record_invocation(self, duration_ms: float, success: bool = True) -> None:
        """Record a tool invocation."""
        self.invocation_count += 1
        if not success:
            self.error_count += 1

        self.total_duration_ms += duration_ms
        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        self.last_invoked = time.time()

    @property
    def avg_duration_ms(self) -> float:
        """Calculate average duration."""
        if self.invocation_count == 0:
            return 0.0
        return self.total_duration_ms / self.invocation_count

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.invocation_count == 0:
            return 100.0
        successes = self.invocation_count - self.error_count
        return (successes / self.invocation_count) * 100.0


class MetricsCollector:
    """Thread-safe metrics collector for MCP operations."""

    def __init__(self) -> None:
        self._tool_metrics: Dict[str, ToolMetrics] = defaultdict(ToolMetrics)
        self._request_count = 0
        self._error_count = 0
        self._lock = Lock()
        self._start_time = time.time()

    def record_tool_invocation(
        self, tool_name: str, duration_ms: float, success: bool = True
    ) -> None:
        """Record a tool invocation with timing and success status."""
        with self._lock:
            self._tool_metrics[tool_name].record_invocation(duration_ms, success)
            self._request_count += 1
            if not success:
                self._error_count += 1

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        with self._lock:
            uptime_seconds = time.time() - self._start_time

            tool_stats: Dict[str, Dict[str, Any]] = {}
            for tool_name, metrics in self._tool_metrics.items():
                tool_stats[tool_name] = {
                    "invocations": metrics.invocation_count,
                    "errors": metrics.error_count,
                    "success_rate_pct": round(metrics.success_rate, 2),
                    "avg_duration_ms": round(metrics.avg_duration_ms, 2),
                    "min_duration_ms": (
                        round(metrics.min_duration_ms, 2)
                        if metrics.min_duration_ms != float("inf")
                        else None
                    ),
                    "max_duration_ms": round(metrics.max_duration_ms, 2),
                    "last_invoked_ago_s": (
                        round(time.time() - metrics.last_invoked, 2)
                        if metrics.last_invoked
                        else None
                    ),
                }

            return {
                "uptime_seconds": round(uptime_seconds, 2),
                "total_requests": self._request_count,
                "total_errors": self._error_count,
                "error_rate_pct": (
                    round((self._error_count / self._request_count) * 100, 2)
                    if self._request_count > 0
                    else 0.0
                ),
                "requests_per_second": (
                    round(self._request_count / uptime_seconds, 2)
                    if uptime_seconds > 0
                    else 0.0
                ),
                "tools": tool_stats,
            }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._tool_metrics.clear()
            self._request_count = 0
            self._error_count = 0
            self._start_time = time.time()


# Global metrics collector instance
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics_collector() -> None:
    """Reset the global metrics collector."""
    global _metrics_collector
    _metrics_collector = None


__all__ = [
    "ToolMetrics",
    "MetricsCollector",
    "get_metrics_collector",
    "reset_metrics_collector",
]
