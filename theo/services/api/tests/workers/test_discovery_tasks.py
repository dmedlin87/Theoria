"""Tests for the lightweight discovery task helpers."""

from __future__ import annotations

import importlib
import sys

import pytest


@pytest.fixture(scope="module")
def tasks_module():
    """Load the real discovery task module instead of the test stub."""

    module_name = "theo.services.api.app.discoveries.tasks"
    package_name = "theo.services.api.app.discoveries"

    original_tasks = sys.modules.pop(module_name, None)
    original_package = sys.modules.pop(package_name, None)

    module = importlib.import_module(module_name)
    try:
        yield module
    finally:
        sys.modules.pop(module_name, None)
        if original_package is not None:
            sys.modules[package_name] = original_package
        if original_tasks is not None:
            sys.modules[module_name] = original_tasks


@pytest.fixture(autouse=True)
def reset_tasks_session_factory(
    monkeypatch: pytest.MonkeyPatch, tasks_module
) -> None:
    """Ensure each test starts with an empty session factory cache."""

    monkeypatch.setitem(tasks_module.__dict__, "_SESSION_FACTORY", None)


def test_get_session_factory_is_memoised(monkeypatch: pytest.MonkeyPatch, tasks_module) -> None:
    calls: list[object] = []

    class DummyEngine:
        pass

    def fake_get_engine() -> DummyEngine:
        calls.append(object())
        return DummyEngine()

    monkeypatch.setitem(tasks_module.__dict__, "get_engine", fake_get_engine)

    first = tasks_module._get_session_factory()
    second = tasks_module._get_session_factory()

    assert first is second
    assert len(calls) == 1


def test_run_discovery_refresh_uses_single_service(
    monkeypatch: pytest.MonkeyPatch, tasks_module
) -> None:
    class FakeSession:
        def __init__(self):
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.closed = True

    session = FakeSession()
    monkeypatch.setitem(
        tasks_module.__dict__, "_get_session_factory", lambda: lambda: session
    )

    created_services: list[FakeDiscoveryService] = []

    class FakeDiscoveryService:
        def __init__(self, received_session):
            created_services.append(self)
            assert received_session is session

        def refresh_user_discoveries(self, user_id: str) -> None:
            assert user_id == "user-123"

    monkeypatch.setitem(
        tasks_module.__dict__, "DiscoveryService", FakeDiscoveryService
    )

    tasks_module.run_discovery_refresh("user-123")

    assert len(created_services) == 1
    assert session.closed is True


def test_schedule_discovery_refresh_requires_truthy_user_id(tasks_module) -> None:
    class Recorder:
        def __init__(self):
            self.calls: list[tuple] = []

        def add_task(self, func, *args, **kwargs):
            self.calls.append((func, args, kwargs))

    tasks = Recorder()
    tasks_module.schedule_discovery_refresh(tasks, None)
    assert tasks.calls == []

    tasks_module.schedule_discovery_refresh(tasks, "user-456")
    assert tasks.calls == [(tasks_module.run_discovery_refresh, ("user-456",), {})]

