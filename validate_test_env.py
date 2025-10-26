#!/usr/bin/env python3
"""Validate that the local test environment has the expected plugins."""

from __future__ import annotations

import importlib
import importlib.util
from typing import Iterable, Tuple


PluginSpec = Tuple[str, str]


REQUIRED_PLUGINS: Iterable[PluginSpec] = (
    ("pytest", "pytest>=8.3,<9"),
    ("xdist", "pytest-xdist==3.6.1"),
    ("pytest_cov", "pytest-cov==5.0.0"),
    ("pytest_timeout", "pytest-timeout==2.3.1"),
)

OPTIONAL_PLUGINS: Iterable[PluginSpec] = (
    ("pytest_randomly", "pytest-randomly==3.15.0"),
    ("pytest_profiling", "pytest-profiling==1.7.0"),
)


def _check_plugin(module_name: str) -> bool:
    """Return True if *module_name* can be imported."""

    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return False

    try:
        importlib.import_module(module_name)
    except ImportError:
        return False

    return True


def _describe_status(module_name: str, requirement: str) -> str:
    available = _check_plugin(module_name)
    icon = "✅" if available else "❌"
    return f"  {icon} {requirement}"


def _report_group(title: str, specs: Iterable[PluginSpec]) -> bool:
    print(title)
    all_present = True
    for module_name, requirement in specs:
        status = _describe_status(module_name, requirement)
        print(status)
        if status.startswith("  ❌"):
            all_present = False
    print()
    return all_present


def main() -> int:
    print("🔍 Validating test environment...\n")

    required_ok = _report_group("Required plugins:", REQUIRED_PLUGINS)
    _report_group("Optional plugins:", OPTIONAL_PLUGINS)

    if required_ok:
        print("✅ Test environment is ready!")
        return 0

    print("❗ Missing required dependencies. Run: pip install -e '.[dev]'")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
