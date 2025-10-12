"""Pytest plugin that stubs coverage options when pytest-cov is unavailable."""

from __future__ import annotations

import pytest

try:  # pragma: no cover - optional dependency in local test harness
    import pytest_cov  # type: ignore  # noqa: F401

    _HAS_PYTEST_COV = True
except ModuleNotFoundError:  # pragma: no cover - executed when plugin is missing
    _HAS_PYTEST_COV = False


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register shim coverage options when pytest-cov is not installed."""

    if _HAS_PYTEST_COV:
        return

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
