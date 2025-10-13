"""Tests for the code quality CLI helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:  # pragma: no branch - defensive guard
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from theo.services.cli import code_quality


def test_execute_rejects_commands_outside_allowlist() -> None:
    request = code_quality.CheckRequest(label="bad", command=("echo", "hello"))

    outcome = code_quality._execute(request)

    assert not outcome.succeeded
    assert outcome.error is not None
    assert "allowlist" in outcome.error


def test_execute_runs_validated_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, capture_output, text, check):  # type: ignore[no-untyped-def]
        captured["command"] = tuple(command)
        returncode = 0
        return SimpleNamespace(
            returncode=returncode,
            stdout="ok",
            stderr="",
        )

    monkeypatch.setattr(code_quality.subprocess, "run", fake_run)

    request = code_quality.CheckRequest(label="ruff", command=("ruff", "check"))

    outcome = code_quality._execute(request)

    assert outcome.succeeded
    assert captured["command"] == ("ruff", "check")


def test_validate_command_rejects_pathlike_program() -> None:
    with pytest.raises(ValueError):
        code_quality._validate_command(("../ruff", "check"))


def test_format_command_quotes_arguments_with_spaces() -> None:
    formatted = code_quality._format_command(
        ("ruff", "--config", "path with spaces.toml")
    )

    assert formatted == "ruff --config 'path with spaces.toml'"


def test_build_checks_constructs_expected_requests() -> None:
    checks = code_quality._build_checks(
        ruff_paths=[Path("pkg"), Path("tests")],
        pytest_paths=[Path("tests/unit"), Path("tests/integration")],
        mypy_paths=[Path("pkg")],
        skip_ruff=False,
        skip_pytest=False,
        include_mypy=True,
        ruff_args=("--fix",),
        pytest_args=("-q", "-k", "pattern"),
        mypy_args=("--strict",),
        mypy_config=Path("mypy.ini"),
    )

    assert [check.label for check in checks] == [
        "ruff (pkg)",
        "ruff (tests)",
        "pytest",
        "mypy",
    ]
    assert checks[0].command == ["ruff", "check", "pkg", "--fix"]
    assert checks[1].command == ["ruff", "check", "tests", "--fix"]
    assert checks[2].command == [
        "pytest",
        "tests/unit",
        "tests/integration",
        "-q",
        "-k",
        "pattern",
    ]
    assert checks[3].command == [
        "mypy",
        "--config-file",
        "mypy.ini",
        "pkg",
        "--strict",
    ]
    assert checks[3].optional is True


def test_build_checks_respects_skip_flags() -> None:
    checks = code_quality._build_checks(
        ruff_paths=[Path("pkg")],
        pytest_paths=[Path("tests")],
        mypy_paths=[Path("pkg")],
        skip_ruff=True,
        skip_pytest=True,
        include_mypy=False,
        ruff_args=(),
        pytest_args=(),
        mypy_args=(),
        mypy_config=None,
    )

    assert checks == []

