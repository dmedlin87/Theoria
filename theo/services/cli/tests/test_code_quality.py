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

