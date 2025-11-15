"""CLI helpers for refreshing pgvector HNSW indexes."""

from __future__ import annotations

import json

import click

from typing import Callable, cast

from celery.app.task import Task
from importlib import import_module

from theo.application.services.bootstrap import resolve_application


def _bootstrap_application() -> None:
    """Initialise application services for the CLI invocation."""

    resolve_application()


def _load_refresh_task() -> Task:
    module = import_module("theo.infrastructure.api.app.workers.tasks")
    task = getattr(module, "refresh_hnsw")
    return cast(Task, task)


_BOOTSTRAP: Callable[[], None] = _bootstrap_application
_TASK_LOADER: Callable[[], Task] = _load_refresh_task


def configure_refresh_hnsw_cli(
    *,
    bootstrapper: Callable[[], None] | None = None,
    task_loader: Callable[[], Task] | None = None,
) -> None:
    """Configure dependency hooks used by the refresh CLI."""

    global _BOOTSTRAP, _TASK_LOADER
    if bootstrapper is None and task_loader is None:
        _BOOTSTRAP = _bootstrap_application
        _TASK_LOADER = _load_refresh_task
        return
    if bootstrapper is not None:
        _BOOTSTRAP = bootstrapper
    if task_loader is not None:
        _TASK_LOADER = task_loader


@click.command()
@click.option(
    "--sample-queries",
    default=25,
    type=click.IntRange(1, 500),
    show_default=True,
    help="Number of random passage embeddings to sample for recall checks.",
)
@click.option(
    "--top-k",
    default=10,
    type=click.IntRange(1, 200),
    show_default=True,
    help="Result window to evaluate recall against.",
)
@click.option(
    "--enqueue/--run-local",
    "enqueue",
    default=True,
    show_default=True,
    help="Queue the Celery task or run synchronously for immediate feedback.",
)
def main(sample_queries: int, top_k: int, enqueue: bool) -> None:
    """Trigger the background refresh job or run it inline."""

    _BOOTSTRAP()
    task = _TASK_LOADER()

    if enqueue:
        async_result = task.delay(
            None, sample_queries=sample_queries, top_k=top_k
        )
        task_id = getattr(async_result, "id", None)
        if task_id:
            click.echo(f"Queued refresh_hnsw task: {task_id}")
        else:
            click.echo("Queued refresh_hnsw task.")
        return

    metrics = task.run(
        None, sample_queries=sample_queries, top_k=top_k
    )
    click.echo("HNSW index refreshed synchronously.")
    click.echo(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    main()
