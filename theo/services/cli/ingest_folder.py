"""Bulk ingestion CLI for walking folders of source files."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Callable, Iterable, Iterator
from uuid import uuid4

import click
import httpx
from sqlalchemy.orm import Session

from ..api.app.core.database import get_engine
from ..api.app.db.models import Document
from ..api.app.enrich import MetadataEnricher
from ..api.app.ingest.pipeline import run_pipeline_for_file
from ..api.app.workers import tasks as worker_tasks


SUPPORTED_TRANSCRIPT_EXTENSIONS = {".vtt", ".webvtt", ".srt"}
SUPPORTED_TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".html", ".htm"}

POST_BATCH_CHOICES = {"tags", "summaries", "biblio"}


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


def _parse_post_batch_steps(values: tuple[str, ...]) -> set[str]:
    steps: set[str] = set()
    for raw_value in values:
        for part in raw_value.split(","):
            step = part.strip().lower()
            if not step:
                continue
            if step not in POST_BATCH_CHOICES:
                allowed = ", ".join(sorted(POST_BATCH_CHOICES))
                raise click.BadParameter(
                    f"Invalid post-batch step '{step}'. Allowed values: {allowed}."
                )
            steps.add(step)
    return steps


def _post_batch_tags(session: Session, document_ids: Iterable[str]) -> None:
    enricher = MetadataEnricher()
    click.echo("   Running post-batch step: tags")
    for doc_id in document_ids:
        document = session.get(Document, doc_id)
        if document is None:
            click.echo(f"     [post-batch:tags] skipped missing document {doc_id}")
            continue
        try:
            enriched = enricher.enrich_document(session, document)
        except Exception as exc:  # pragma: no cover - defensive logging
            click.echo(f"     [post-batch:tags] failed for {doc_id}: {exc}", err=True)
            continue
        status = "enriched" if enriched else "no updates"
        click.echo(f"     [post-batch:tags] {status} for {doc_id}")


def _post_batch_biblio(_: Session, document_ids: Iterable[str]) -> None:
    click.echo("   Running post-batch step: biblio")
    for doc_id in document_ids:
        try:
            async_result = worker_tasks.enrich_document.delay(doc_id)
        except Exception as exc:  # pragma: no cover - defensive logging
            click.echo(f"     [post-batch:biblio] failed for {doc_id}: {exc}", err=True)
            continue
        task_id = getattr(async_result, "id", None)
        suffix = f" task {task_id}" if task_id else ""
        click.echo(f"     [post-batch:biblio] queued{suffix} for {doc_id}")


def _post_batch_summaries(_: Session, document_ids: Iterable[str]) -> None:
    click.echo("   Running post-batch step: summaries")
    base_url = (
        os.environ.get("API_BASE_URL")
        or os.environ.get("NEXT_PUBLIC_API_BASE_URL")
        or "http://127.0.0.1:8000"
    )
    base_url = base_url.rstrip("/")

    with httpx.Client(timeout=10.0) as client:
        for doc_id in document_ids:
            try:
                response = client.post(
                    f"{base_url}/jobs/summaries",
                    json={"document_id": doc_id},
                )
            except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
                click.echo(
                    f"     [post-batch:summaries] failed for {doc_id}: {exc}",
                    err=True,
                )
                continue
            if response.status_code >= 400:
                click.echo(
                    "     [post-batch:summaries] failed for"
                    f" {doc_id}: {response.status_code} {response.text}",
                    err=True,
                )
                continue
            click.echo(f"     [post-batch:summaries] queued for {doc_id}")


POST_BATCH_HANDLERS: dict[str, Callable[[Session, Iterable[str]], None]] = {
    "tags": _post_batch_tags,
    "biblio": _post_batch_biblio,
    "summaries": _post_batch_summaries,
}


def _run_post_batch_operations(
    session: Session, document_ids: list[str], steps: set[str]
) -> None:
    for step in sorted(steps):
        handler = POST_BATCH_HANDLERS.get(step)
        if handler is None:  # pragma: no cover - guarded by parser
            continue
        handler(session, document_ids)


def _ingest_batch_via_api(
    batch: list[FolderItem],
    overrides: dict[str, object],
    post_batch_steps: set[str] | None = None,
) -> list[str]:
    engine = get_engine()
    document_ids: list[str] = []
    with Session(engine) as session:
        for item in batch:
            frontmatter = dict(overrides)
            document = run_pipeline_for_file(session, item.path, frontmatter)
            document_ids.append(document.id)
        if post_batch_steps:
            _run_post_batch_operations(session, document_ids, post_batch_steps)
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
@click.option(
    "--post-batch",
    "post_batch_steps",
    multiple=True,
    help=(
        "Comma-separated post-ingest operations to run after each API batch "
        "(options: summaries, tags, biblio)."
    ),
)
def ingest_folder(
    path: Path,
    *,
    mode: str,
    batch_size: int,
    dry_run: bool,
    metadata_overrides: tuple[str, ...],
    post_batch_steps: tuple[str, ...],
) -> None:
    """Queue every supported file in PATH for ingestion."""

    overrides = _parse_metadata_overrides(metadata_overrides)
    items = list(_walk_folder(path))
    normalized_post_batch = _parse_post_batch_steps(post_batch_steps)
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
            document_ids = _ingest_batch_via_api(batch, overrides, normalized_post_batch)
            for item, doc_id in zip(batch, document_ids):
                click.echo(f"   Processed {item.path} → document {doc_id}")
        else:
            if normalized_post_batch:
                click.echo("   Post-batch steps require API mode; skipping.")
            task_ids = _queue_batch_via_worker(batch, overrides)
            for item, task_id in zip(batch, task_ids):
                click.echo(f"   Queued {item.path} → task {task_id}")


if __name__ == "__main__":
    ingest_folder()
