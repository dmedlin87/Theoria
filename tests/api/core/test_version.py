"""Tests for the application version facade."""
from __future__ import annotations

import types

import pytest

from tests.api.core import reload_facade


def test_get_git_sha_invokes_git_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    module = reload_facade("theo.application.facades.version")
    module.get_git_sha.cache_clear()

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/git")

    def fake_run(*_args, **_kwargs):
        return types.SimpleNamespace(stdout="deadbeef\n")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.get_git_sha() == "deadbeef"
