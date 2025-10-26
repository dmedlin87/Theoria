import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import launcher_helpers


class DummyCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_detect_runtime_success(monkeypatch):
    calls = []

    def fake_which(cmd):
        calls.append(cmd)
        if cmd == "python":
            return None
        if cmd == "python3":
            return "/usr/bin/python3"
        raise AssertionError(f"Unexpected command {cmd}")

    def fake_run(cmd, capture_output, text, timeout, check):
        assert cmd == ["/usr/bin/python3", "--version"]
        return DummyCompletedProcess(stdout="Python 3.11.6\n")

    runtime = {
        "name": "Python",
        "commands": ["python", "python3"],
        "args": ["--version"],
        "category": "local",
        "guidance": "Install Python",
        "installers": [],
    }

    monkeypatch.setattr(launcher_helpers.shutil, "which", fake_which)
    monkeypatch.setattr(launcher_helpers.subprocess, "run", fake_run)

    result = launcher_helpers.detect_runtime(runtime)

    assert calls == ["python", "python3"]
    assert result == {
        "name": "Python",
        "present": True,
        "version": "Python 3.11.6",
        "command": "/usr/bin/python3",
        "category": "local",
        "guidance": "Install Python",
        "installers": [],
    }


def test_detect_runtime_failure(monkeypatch):
    sequence = {
        "python": "/usr/bin/python",
        "python3": "/usr/bin/python3",
    }
    attempts = []

    def fake_which(cmd):
        attempts.append(cmd)
        return sequence.get(cmd)

    def fake_run(cmd, capture_output, text, timeout, check):
        if cmd[0] == "/usr/bin/python":
            raise OSError("broken runtime")
        return DummyCompletedProcess(returncode=1, stderr="error")

    runtime = {
        "name": "Python",
        "commands": ["python", "python3"],
        "args": ["--version"],
        "category": "local",
    }

    monkeypatch.setattr(launcher_helpers.shutil, "which", fake_which)
    monkeypatch.setattr(launcher_helpers.subprocess, "run", fake_run)

    result = launcher_helpers.detect_runtime(runtime)

    assert attempts == ["python", "python3"]
    assert result["present"] is False
    assert result["version"] is None
    assert result["command"] is None


def test_detect_docker_compose_success(monkeypatch):
    paths = {"docker": "/usr/bin/docker"}

    def fake_which(cmd):
        return paths.get(cmd)

    def fake_run(cmd, capture_output, text, timeout, check):
        assert cmd == ["/usr/bin/docker", "compose", "version"]
        return DummyCompletedProcess(stdout="Docker Compose version v2.24.5\n")

    monkeypatch.setattr(launcher_helpers.shutil, "which", fake_which)
    monkeypatch.setattr(launcher_helpers.subprocess, "run", fake_run)

    result = launcher_helpers.detect_docker_compose()

    assert result["present"] is True
    assert result["version"] == "Docker Compose version v2.24.5"
    assert result["command"] == "/usr/bin/docker compose version"


def test_detect_docker_compose_missing(monkeypatch):
    def fake_which(cmd):
        return None

    monkeypatch.setattr(launcher_helpers.shutil, "which", fake_which)
    monkeypatch.setattr(
        launcher_helpers.subprocess,
        "run",
        lambda *args, **kwargs: DummyCompletedProcess(returncode=0),
    )

    result = launcher_helpers.detect_docker_compose()

    assert result["present"] is False
    assert result["version"] is None
    assert result["command"] is None
    assert result["category"] == "container"
    assert result["guidance"] == "Install Docker Desktop to use docker compose fallback."
    assert result["installers"]


def test_command_check_aggregates(monkeypatch):
    fake_definitions = [
        {"name": "Python"},
        {"name": "Node"},
    ]
    outputs = [
        {"name": "Python", "present": True},
        {"name": "Node", "present": False},
    ]

    compose_result = {"name": "Docker Compose", "present": True}

    def fake_detect_runtime(runtime):
        index = fake_definitions.index(runtime)
        return outputs[index]

    def fake_detect_docker_compose():
        return compose_result

    monkeypatch.setattr(launcher_helpers, "RUNTIME_DEFINITIONS", fake_definitions)
    monkeypatch.setattr(launcher_helpers, "detect_runtime", fake_detect_runtime)
    monkeypatch.setattr(launcher_helpers, "detect_docker_compose", fake_detect_docker_compose)

    report = launcher_helpers.command_check(Path("/tmp/project"))

    assert report["project_root"] == "/tmp/project"
    assert report["runtimes"] == outputs + [compose_result]
    assert "generated_at" in report


def test_output_prereq_report_json(monkeypatch, capsys):
    report = {"runtimes": []}
    launcher_helpers.output_prereq_report(report, "json")
    captured = capsys.readouterr().out
    assert json.loads(captured) == report


def test_output_prereq_report_text(capsys):
    report = {
        "runtimes": [
            {"name": "Python", "present": True, "version": "3.11.6"},
            {"name": "Docker", "present": False, "version": None},
        ]
    }

    launcher_helpers.output_prereq_report(report, "text")
    output = capsys.readouterr().out.strip().splitlines()

    assert output[0] == "Runtime prerequisite report"
    assert " - Python: OK [3.11.6]" in output[1]
    assert " - Docker: MISSING [(unknown)]" in output[2]


def test_check_prereqs_invokes_dependencies(monkeypatch):
    fake_report = {"runtimes": ["data"]}
    called = {}

    def fake_command_check(path):
        called["command_check"] = path
        return fake_report

    def fake_output(report, fmt):
        called["output"] = (report, fmt)

    monkeypatch.setattr(launcher_helpers, "command_check", fake_command_check)
    monkeypatch.setattr(launcher_helpers, "output_prereq_report", fake_output)

    args = SimpleNamespace(project_root=Path("/workspace"), format="text")
    launcher_helpers.check_prereqs(args)

    assert called["command_check"] == Path("/workspace")
    assert called["output"] == (fake_report, "text")


def test_ensure_crypto_available_missing(monkeypatch):
    monkeypatch.setattr(launcher_helpers, "x509", None)
    monkeypatch.setattr(launcher_helpers, "rsa", None)

    with pytest.raises(RuntimeError) as exc:
        launcher_helpers.ensure_crypto_available()

    assert "cryptography" in str(exc.value)


def test_ensure_crypto_available_present(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(launcher_helpers, "x509", sentinel)
    monkeypatch.setattr(launcher_helpers, "rsa", sentinel)

    launcher_helpers.ensure_crypto_available()  # should not raise
