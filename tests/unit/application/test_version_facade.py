"""Unit tests for the version facade helpers."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

version = importlib.import_module("theo.application.facades.version")


@pytest.fixture(scope="session")
def integration_database_url() -> str:
    """Provide a lightweight stand-in for the global integration database fixture."""

    return "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def clear_version_cache() -> None:
    """Ensure cached values do not leak between tests."""

    version.get_git_sha.cache_clear()
    try:
        yield
    finally:
        version.get_git_sha.cache_clear()


def test_get_git_sha_returns_none_when_git_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """When git is unavailable the helper should simply return ``None``."""

    monkeypatch.setattr(version.shutil, "which", lambda _: None)

    assert version.get_git_sha() is None


def test_get_git_sha_returns_trimmed_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful git command should have its stdout trimmed before returning."""

    calls: list[str] = []

    def fake_which(binary: str) -> str:
        calls.append(binary)
        return "/usr/bin/git"

    def fake_run(*_: object, **__: object) -> SimpleNamespace:
        return SimpleNamespace(stdout="abcdef123456\n")

    monkeypatch.setattr(version.shutil, "which", fake_which)
    monkeypatch.setattr(version.subprocess, "run", fake_run)

    first = version.get_git_sha()
    second = version.get_git_sha()

    assert first == "abcdef123456"
    assert second == "abcdef123456"
    assert calls == ["git"]  # cached result prevents subsequent git invocations


def test_get_git_sha_handles_git_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper should swallow git errors and return ``None``."""

    def fake_run(*_: object, **__: object) -> None:
        raise version.subprocess.CalledProcessError(
            returncode=1, cmd=["git", "rev-parse", "HEAD"]
        )

    monkeypatch.setattr(version.shutil, "which", lambda _: "/usr/bin/git")
    monkeypatch.setattr(version.subprocess, "run", fake_run)

    assert version.get_git_sha() is None


def test_get_git_sha_handles_git_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper should return ``None`` when git disappears between checks."""

    def fake_run(*_: object, **__: object) -> None:
        raise FileNotFoundError("git not available")

    monkeypatch.setattr(version.shutil, "which", lambda _: "/usr/bin/git")
    monkeypatch.setattr(version.subprocess, "run", fake_run)

    assert version.get_git_sha() is None
