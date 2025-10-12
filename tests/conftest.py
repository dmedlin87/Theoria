from __future__ import annotations

import os
import sys
from pathlib import Path

try:  # pragma: no cover - optional dependency in local test harness
    import pytest_cov  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - executed when plugin missing
    def pytest_addoption(parser):
        """Register a minimal stub for pytest-cov options when plugin is absent."""

        group = parser.getgroup("cov", "coverage reporting (stub)")
        group.addoption(
            "--cov",
            action="append",
            default=[],
            dest="cov_source",
            metavar="PATH",
            help="Stub option allowing tests to run without pytest-cov installed.",
        )
        group.addoption(
            "--cov-report",
            action="append",
            default=[],
            dest="cov_report",
            metavar="TYPE",
            help="Stub option allowing tests to run without pytest-cov installed.",
        )
        group.addoption(
            "--cov-fail-under",
            action="store",
            default=None,
            dest="cov_fail_under",
            type=float,
            help="Stub option allowing tests to run without pytest-cov installed.",
        )

os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
