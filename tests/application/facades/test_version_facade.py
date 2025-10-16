from types import SimpleNamespace
import subprocess

import pytest

from theo.application.facades import version as version_module


@pytest.fixture(autouse=True)
def clear_get_git_sha_cache() -> None:
    version_module.get_git_sha.cache_clear()
    yield
    version_module.get_git_sha.cache_clear()


def test_get_git_sha_returns_none_when_git_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(version_module.shutil, "which", lambda _: None)

    assert version_module.get_git_sha() is None


def test_get_git_sha_returns_trimmed_sha_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(version_module.shutil, "which", lambda _: "/usr/bin/git")
    calls: list[list[str]] = []

    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return SimpleNamespace(stdout="deadbeef\n")

    monkeypatch.setattr(version_module.subprocess, "run", fake_run)

    first = version_module.get_git_sha()
    second = version_module.get_git_sha()

    assert first == "deadbeef"
    assert second == "deadbeef"
    assert calls == [["/usr/bin/git", "rev-parse", "HEAD"]]


def test_get_git_sha_returns_none_when_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(version_module.shutil, "which", lambda _: "/usr/bin/git")

    def raise_error(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=args[0])

    monkeypatch.setattr(version_module.subprocess, "run", raise_error)

    assert version_module.get_git_sha() is None


def test_get_git_sha_returns_none_when_output_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(version_module.shutil, "which", lambda _: "/usr/bin/git")

    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout="   \n\t")

    monkeypatch.setattr(version_module.subprocess, "run", fake_run)

    assert version_module.get_git_sha() is None
