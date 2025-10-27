"""Unit tests for the discovery scheduler background worker."""

from __future__ import annotations

import pytest

from theo.infrastructure.api.app.workers import discovery_scheduler as scheduler_module


@pytest.fixture(autouse=True)
def reset_scheduler_session_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure cached session factories don't leak between tests."""

    monkeypatch.setattr(scheduler_module, "_SESSION_FACTORY", None)


class FakeBackgroundScheduler:
    """Minimal in-memory replacement for :class:`BackgroundScheduler`."""

    def __init__(self, timezone: str | None = None):
        self.timezone = timezone
        self.add_job_calls: list[tuple[tuple, dict]] = []
        self.start_calls = 0
        self.shutdown_calls: list[dict] = []

    def add_job(self, *args, **kwargs) -> None:
        self.add_job_calls.append((args, kwargs))

    def start(self) -> None:
        self.start_calls += 1

    def shutdown(self, **kwargs) -> None:
        self.shutdown_calls.append(kwargs)

def test_start_registers_single_interval_job(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_scheduler = FakeBackgroundScheduler()

    def fake_background_scheduler(**kwargs):
        assert kwargs == {"timezone": "UTC"}
        return fake_scheduler

    monkeypatch.setattr(
        scheduler_module, "BackgroundScheduler", fake_background_scheduler
    )

    scheduler = scheduler_module.DiscoveryScheduler()

    scheduler.start()
    assert len(fake_scheduler.add_job_calls) == 1
    _, job_kwargs = fake_scheduler.add_job_calls[0]
    assert job_kwargs["id"] == "discovery_refresh"
    assert job_kwargs["name"] == "Refresh discoveries for all users"
    assert fake_scheduler.start_calls == 1

    # Duplicate starts do not register extra jobs or restart the scheduler.
    scheduler.start()
    assert len(fake_scheduler.add_job_calls) == 1
    assert fake_scheduler.start_calls == 1


def test_stop_only_shuts_down_when_running(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_scheduler = FakeBackgroundScheduler()
    monkeypatch.setattr(
        scheduler_module, "BackgroundScheduler", lambda **_: fake_scheduler
    )
    scheduler = scheduler_module.DiscoveryScheduler()

    scheduler.stop()
    assert fake_scheduler.shutdown_calls == []

    scheduler.start()
    scheduler.stop()
    assert fake_scheduler.shutdown_calls == [{"wait": True}]


class RecordingSession:
    def __init__(self):
        self.commit_calls = 0
        self.rollback_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_trigger_user_refresh_commits_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RecordingSession()
    sentinel = ["discovery"]

    fake_discovery_repo = object()
    fake_document_repo = object()

    def fake_discovery_repo_factory(received_session):
        assert received_session is session
        return fake_discovery_repo

    def fake_document_repo_factory(received_session):
        assert received_session is session
        return fake_document_repo

    monkeypatch.setattr(
        scheduler_module,
        "SQLAlchemyDiscoveryRepository",
        fake_discovery_repo_factory,
    )
    monkeypatch.setattr(
        scheduler_module,
        "SQLAlchemyDocumentRepository",
        fake_document_repo_factory,
    )

    class StubService:
        def __init__(self, discovery_repo, document_repo):
            assert discovery_repo is fake_discovery_repo
            assert document_repo is fake_document_repo

        def refresh_user_discoveries(self, user_id: str):
            assert user_id == "alice"
            return sentinel

    monkeypatch.setattr(scheduler_module, "DiscoveryService", StubService)

    scheduler = scheduler_module.DiscoveryScheduler()
    result = scheduler.trigger_user_refresh(session, "alice")

    assert result is sentinel
    assert session.commit_calls == 1
    assert session.rollback_calls == 0


def test_trigger_user_refresh_rolls_back_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RecordingSession()

    fake_discovery_repo = object()
    fake_document_repo = object()

    def fake_discovery_repo_factory(received_session):
        assert received_session is session
        return fake_discovery_repo

    def fake_document_repo_factory(received_session):
        assert received_session is session
        return fake_document_repo

    monkeypatch.setattr(
        scheduler_module,
        "SQLAlchemyDiscoveryRepository",
        fake_discovery_repo_factory,
    )
    monkeypatch.setattr(
        scheduler_module,
        "SQLAlchemyDocumentRepository",
        fake_document_repo_factory,
    )

    class ExplodingService:
        def __init__(self, discovery_repo, document_repo):
            assert discovery_repo is fake_discovery_repo
            assert document_repo is fake_document_repo

        def refresh_user_discoveries(self, user_id: str):
            raise RuntimeError("boom")

    monkeypatch.setattr(scheduler_module, "DiscoveryService", ExplodingService)

    scheduler = scheduler_module.DiscoveryScheduler()
    result = scheduler.trigger_user_refresh(session, "bob")

    assert result == []
    assert session.commit_calls == 0
    assert session.rollback_calls == 1


class FakeSession:
    def __init__(self, user_ids: list[str | None]):
        self._user_ids = user_ids
        self.closed = False
        self.rollback_calls = 0
        self.scalars_calls = 0

    def scalars(self, stmt):  # noqa: D401 - matches SQLAlchemy API
        self.scalars_calls += 1
        return list(self._user_ids)

    def rollback(self) -> None:
        self.rollback_calls += 1

    def close(self) -> None:
        self.closed = True


def test_refresh_all_users_skips_falsy_and_reuses_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(["", "alpha", None, "beta"])
    monkeypatch.setattr(scheduler_module, "_get_session_factory", lambda: lambda: session)

    calls: list[tuple[FakeSession, str]] = []

    def fake_trigger(self, bound_session, user_id):
        calls.append((bound_session, user_id))

    monkeypatch.setattr(scheduler_module.DiscoveryScheduler, "trigger_user_refresh", fake_trigger)

    scheduler = scheduler_module.DiscoveryScheduler()
    scheduler._refresh_all_users()

    assert [user_id for _, user_id in calls] == ["alpha", "beta"]
    assert all(call_session is session for call_session, _ in calls)
    assert session.scalars_calls == 1
    assert session.rollback_calls == 0
    assert session.closed is True


def test_refresh_all_users_rolls_back_on_outer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExplodingSession:
        def __init__(self):
            self.rollback_calls = 0
            self.closed = False

        def scalars(self, stmt):
            raise RuntimeError("query failed")

        def rollback(self) -> None:
            self.rollback_calls += 1

        def close(self) -> None:
            self.closed = True

    session = ExplodingSession()
    monkeypatch.setattr(scheduler_module, "_get_session_factory", lambda: lambda: session)

    scheduler = scheduler_module.DiscoveryScheduler()
    scheduler._refresh_all_users()

    assert session.rollback_calls == 1
    assert session.closed is True

