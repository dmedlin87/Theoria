"""Stubs for Celery schedule helpers used in tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _CronSchedule:
    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def __call__(self) -> dict[str, Any]:  # pragma: no cover - compatibility helper
        return {"args": self.args, "kwargs": self.kwargs}


def crontab(*args: Any, **kwargs: Any) -> _CronSchedule:
    """Return an object representing a cron schedule.

    The stub merely records the provided arguments so that test assertions can
    introspect the configured schedule if needed.
    """

    return _CronSchedule(args, dict(kwargs))


__all__ = ["crontab"]
