from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theo.application.services.cli import code_quality as code_quality_module


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_code_quality_runs_selected_checks(monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    calls: list[list[str]] = []

    def _fake_run(command: list[str], capture_output: bool, text: bool, check: bool) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(code_quality_module.subprocess, "run", _fake_run)

    result = runner.invoke(
        code_quality_module.code_quality,
        [
            "--ruff-path",
            "mcp_server",
            "--pytest-path",
            "tests/mcp_tools",
            "--include-mypy",
            "--mypy-path",
            "mcp_server",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        ["ruff", "check", "mcp_server"],
        ["pytest", "tests/mcp_tools", "-q"],
        ["mypy", "mcp_server"],
    ]
    assert "Summary:" in result.output
    assert "✅ ruff (mcp_server)" in result.output


def test_code_quality_reports_required_failures(monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    responses = iter(
        [
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=1, stdout="pytest failure", stderr="boom"),
        ]
    )

    def _fake_run(command: list[str], capture_output: bool, text: bool, check: bool) -> SimpleNamespace:
        return next(responses)

    monkeypatch.setattr(code_quality_module.subprocess, "run", _fake_run)

    result = runner.invoke(code_quality_module.code_quality, [])

    assert result.exit_code == 1
    assert "pytest failure" in result.output
    assert "❌ pytest" in result.output


def test_code_quality_treats_optional_failures_as_warnings(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    responses = iter(
        [
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=1, stdout="", stderr="type error"),
        ]
    )

    def _fake_run(command: list[str], capture_output: bool, text: bool, check: bool) -> SimpleNamespace:
        return next(responses)

    monkeypatch.setattr(code_quality_module.subprocess, "run", _fake_run)

    result = runner.invoke(code_quality_module.code_quality, ["--include-mypy"])

    assert result.exit_code == 0
    assert "⚠️ mypy" in result.output
    assert "Optional checks failed" in result.output


def test_code_quality_strict_mode_escalates_optional_failures(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    responses = iter(
        [
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=1, stdout="", stderr="type error"),
        ]
    )

    def _fake_run(command: list[str], capture_output: bool, text: bool, check: bool) -> SimpleNamespace:
        return next(responses)

    monkeypatch.setattr(code_quality_module.subprocess, "run", _fake_run)

    result = runner.invoke(code_quality_module.code_quality, ["--include-mypy", "--strict"])

    assert result.exit_code == 1
    assert "❌ mypy" in result.output
