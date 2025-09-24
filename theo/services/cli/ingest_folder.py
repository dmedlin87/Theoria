"""Bulk ingestion CLI for walking folders of source files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Iterable, Iterator
from uuid import uuid4

import click
from sqlalchemy.orm import Session

from ..api.app.core.database import get_engine
from ..api.app.ingest.pipeline import run_pipeline_for_file
from ..api.app.workers import tasks as worker_tasks


SUPPORTED_TRANSCRIPT_EXTENSIONS = {".vtt", ".webvtt", ".srt"}
SUPPORTED_TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".html", ".htm"}


@dataclass(frozen=True)
class FolderItem:
    """Represents a discovered file eligible for ingestion."""

    path: Path
    source_type: str


def _detect_source_type(path: Path) -> str:
    """Infer a source type for *path* mirroring the ingestion pipeline rules."""

    ext = path.suffix.lower()
    if ext in {".md", ".markdown"}:
        return "markdown"
    if ext == ".txt" or ext in {".html", ".htm"}:
        return "txt" if ext == ".txt" else "file"
    if ext == ".pdf":
        return "pdf"
    if ext in SUPPORTED_TRANSCRIPT_EXTENSIONS or ext == ".json":
        return "transcript"
    if ext == ".docx":
        return "docx"
    return "file"


def _is_supported(path: Path) -> bool:
    if not path.is_file():
        return False
    ext = path.suffix.lower()
    return (
        ext in SUPPORTED_TRANSCRIPT_EXTENSIONS
        or ext in SUPPORTED_TEXT_EXTENSIONS
        or ext in {".pdf", ".json", ".docx"}
        or not ext
    )


def _walk_folder(path: Path) -> Iterator[FolderItem]:
    candidates: Iterable[Path]
    if path.is_file():
        candidates = [path]
    else:
        candidates = sorted(p for p in path.rglob("*") if _is_supported(p))
    for candidate in candidates:
        if not candidate.is_file() or not _is_supported(candidate):
            continue
        yield FolderItem(path=candidate, source_type=_detect_source_type(candidate))


def _parse_metadata_overrides(pairs: tuple[str, ...]) -> dict[str, object]:
    overrides: dict[str, object] = {}
    for pair in pairs:
        if "=" not in pair:
            raise click.BadParameter("Metadata overrides must be in key=value form")
        key, raw_value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise click.BadParameter("Metadata keys cannot be empty")
        value: object
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value
        overrides[key] = value
    return overrides


def _batched(iterable: Iterable[FolderItem], size: int) -> Iterator[list[FolderItem]]:
    iterator = iter(iterable)
    while True:
        batch = list(islice(iterator, size))
        if not batch:
            return
        yield batch


def _ingest_batch_via_api(batch: list[FolderItem], overrides: dict[str, object]) -> list[str]:
    engine = get_engine()
    document_ids: list[str] = []
    with Session(engine) as session:
        for item in batch:
            frontmatter = dict(overrides)
            document = run_pipeline_for_file(session, item.path, frontmatter)
            document_ids.append(document.id)
    return document_ids


def _queue_batch_via_worker(batch: list[FolderItem], overrides: dict[str, object]) -> list[str]:
    task_ids: list[str] = []
    for item in batch:
        frontmatter = dict(overrides)
        async_result = worker_tasks.process_file.delay(str(uuid4()), str(item.path), frontmatter)
        task_ids.append(async_result.id if hasattr(async_result, "id") else "queued")
    return task_ids


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--mode",
    type=click.Choice(["api", "worker"], case_sensitive=False),
    default="api",
    show_default=True,
    help="Ingestion backend to use.",
)
@click.option(
    "--batch-size",
    type=click.IntRange(min=1),
    default=10,
    show_default=True,
    help="Number of files to process per batch.",
)
@click.option("--dry-run", is_flag=True, help="List files without ingesting them.")
@click.option(
    "--meta",
    "metadata_overrides",
    multiple=True,
    help="Metadata overrides applied to every file (key=value, JSON values allowed).",
)
def ingest_folder(
    path: Path,
    *,
    mode: str,
    batch_size: int,
    dry_run: bool,
    metadata_overrides: tuple[str, ...],
) -> None:
    """Queue every supported file in PATH for ingestion."""

    overrides = _parse_metadata_overrides(metadata_overrides)
    items = list(_walk_folder(path))
    if not items:
        click.echo("No supported files found.")
        return

    click.echo(f"Discovered {len(items)} supported file(s) in {path}.")
    for batch_number, batch in enumerate(_batched(items, batch_size), start=1):
        click.echo(f"Batch {batch_number}: {len(batch)} file(s).")
        for item in batch:
            click.echo(f" - [{item.source_type}] {item.path}")

        if dry_run:
            click.echo("Dry-run enabled; skipping ingestion.")
            continue

        if mode.lower() == "api":
            document_ids = _ingest_batch_via_api(batch, overrides)
            for item, doc_id in zip(batch, document_ids):
                click.echo(f"   Processed {item.path} → document {doc_id}")
        else:
            task_ids = _queue_batch_via_worker(batch, overrides)
            for item, task_id in zip(batch, task_ids):
                click.echo(f"   Queued {item.path} → task {task_id}")


if __name__ == "__main__":
    ingest_folder()
