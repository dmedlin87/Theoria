from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest
from click.testing import CliRunner

from tests.fixtures.embedding import embedding_service_patch


@pytest.fixture()
def refresh_cli_module(
    monkeypatch: pytest.MonkeyPatch, embedding_service_patch
):
    """Import the refresh_hnsw CLI module with bootstrap patched out."""

    celery_module = ModuleType("celery")
    celery_app_module = ModuleType("celery.app")
    celery_task_module = ModuleType("celery.app.task")
    celery_task_module.Task = type("Task", (), {})
    celery_module.app = celery_app_module
    celery_app_module.task = celery_task_module
    monkeypatch.setitem(sys.modules, "celery", celery_module)
    monkeypatch.setitem(sys.modules, "celery.app", celery_app_module)
    monkeypatch.setitem(sys.modules, "celery.app.task", celery_task_module)
    fake_tasks_module = ModuleType("theo.infrastructure.api.app.workers.tasks")
    fake_tasks_module.refresh_hnsw = SimpleNamespace(
        delay=lambda *args, **kwargs: SimpleNamespace(id=None),
        run=lambda *args, **kwargs: {},
    )
    monkeypatch.setitem(
        sys.modules, "theo.infrastructure.api.app.workers.tasks", fake_tasks_module
    )
    monkeypatch.delitem(
        sys.modules, "theo.services.cli.refresh_hnsw", raising=False
    )
    module = importlib.import_module("theo.services.cli.refresh_hnsw")
    module = importlib.reload(module)
    module.configure_refresh_hnsw_cli(bootstrapper=lambda: None)
    try:
        yield module
    finally:
        module.configure_refresh_hnsw_cli()


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class _FakeTask:
    def __init__(self) -> None:
        self.delay_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.run_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def delay(self, *args: object, **kwargs: object) -> SimpleNamespace:
        self.delay_calls.append((args, kwargs))
        return SimpleNamespace(id="job-123")

    def run(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.run_calls.append((args, kwargs))
        return {"status": "ok", "sampleQueries": kwargs.get("sample_queries")}


def test_main_enqueues_task_by_default(
    refresh_cli_module, runner: CliRunner
) -> None:
    fake_task = _FakeTask()
    refresh_cli_module.configure_refresh_hnsw_cli(
        bootstrapper=lambda: None, task_loader=lambda: fake_task
    )

    result = runner.invoke(refresh_cli_module.main, [])

    assert result.exit_code == 0
    assert fake_task.delay_calls == [((None,), {"sample_queries": 25, "top_k": 10})]
    assert fake_task.run_calls == []
    assert "Queued refresh_hnsw task: job-123" in result.output


def test_main_runs_task_inline_when_requested(
    refresh_cli_module, runner: CliRunner
) -> None:
    fake_task = _FakeTask()
    refresh_cli_module.configure_refresh_hnsw_cli(
        bootstrapper=lambda: None, task_loader=lambda: fake_task
    )

    result = runner.invoke(
        refresh_cli_module.main,
        ["--run-local", "--sample-queries", "17", "--top-k", "4"],
    )

    assert result.exit_code == 0
    assert fake_task.delay_calls == []
    assert fake_task.run_calls == [((None,), {"sample_queries": 17, "top_k": 4})]
    assert "HNSW index refreshed synchronously." in result.output
    assert '"sampleQueries": 17' in result.output


def test_main_enqueues_task_without_identifier(
    refresh_cli_module, runner: CliRunner
) -> None:
    class _ResultWithoutId:
        def __init__(self) -> None:
            self.called_with: tuple[tuple[object, ...], dict[str, object]] | None = None

        def delay(self, *args: object, **kwargs: object) -> "_ResultWithoutId":
            self.called_with = (args, kwargs)
            return self

    fake_task = _ResultWithoutId()
    refresh_cli_module.configure_refresh_hnsw_cli(
        bootstrapper=lambda: None, task_loader=lambda: fake_task
    )

    result = runner.invoke(
        refresh_cli_module.main,
        ["--enqueue", "--sample-queries", "11", "--top-k", "6"],
    )

    assert result.exit_code == 0
    assert fake_task.called_with == ((None,), {"sample_queries": 11, "top_k": 6})
    assert "Queued refresh_hnsw task." in result.output


def test_main_rejects_out_of_range_values(
    refresh_cli_module, runner: CliRunner
) -> None:
    result = runner.invoke(
        refresh_cli_module.main,
        ["--sample-queries", "0"],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--sample-queries'" in result.output

    result = runner.invoke(
        refresh_cli_module.main,
        ["--top-k", "201"],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--top-k'" in result.output
