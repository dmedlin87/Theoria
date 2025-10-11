"""Bulk ingestion CLI for walking folders of source files."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence, cast
from uuid import uuid4

import click
import httpx
from sqlalchemy.orm import Session
from urllib.parse import urlparse

from ..api.app.core.database import get_engine
from ..api.app.core.settings import get_settings
from ..api.app.db.models import Document
from ..api.app.enrich import MetadataEnricher
from ..api.app.ingest.pipeline import (
    PipelineDependencies,
    run_pipeline_for_file,
    run_pipeline_for_url,
)
from ..api.app.workers import tasks as worker_tasks
from ..api.app.telemetry import log_workflow_event

SUPPORTED_TRANSCRIPT_EXTENSIONS = {".vtt", ".webvtt", ".srt"}
SUPPORTED_TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".html", ".htm"}

POST_BATCH_CHOICES = {"tags", "summaries", "biblio"}

DEFAULT_COLLECTION = "uploads"
DEFAULT_AUTHOR = "Theo Engine"


@dataclass(frozen=True)
class IngestItem:
    """Represents a discovered ingestion target."""

    source_type: str
    path: Path | None = None
    url: str | None = None

    @property
    def is_remote(self) -> bool:
        return self.url is not None

    @property
    def label(self) -> str:
        if self.path is not None:
            return str(self.path)
        return str(self.url or "")


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


def _detect_url_source_type(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    return "web_page"


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


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


def _discover_items(
    sources: Sequence[str], allowlist: Sequence[Path] | None = None
) -> list[IngestItem]:
    """Expand a list of user-supplied sources into ingestable items."""

    normalized_allowlist: tuple[Path, ...] | None = None
    if allowlist is not None:
        normalized_allowlist = tuple(
            Path(root).expanduser().resolve(strict=False) for root in allowlist
        )

    items: list[IngestItem] = []
    for raw_source in sources:
        source = raw_source.strip()
        if not source:
            continue
        if _looks_like_url(source):
            items.append(
                IngestItem(url=source, source_type=_detect_url_source_type(source))
            )
            continue

        path = Path(source).expanduser()
        if not path.exists():
            raise ValueError(f"Path '{source}' does not exist")
        if normalized_allowlist is not None:
            resolved_path = path.resolve()
            if not any(
                resolved_path == root or resolved_path.is_relative_to(root)
                for root in normalized_allowlist
            ):
                raise ValueError(
                    f"Path '{source}' is not within an allowed ingest root"
                )
        if not path.is_dir() and not _is_supported(path):
            continue
        items.extend(_walk_folder(path))
    return items


def _walk_folder(path: Path) -> Iterator[IngestItem]:
    candidates: Iterable[Path]
    if path.is_file():
        candidates = [path]
    else:
        candidates = sorted(p for p in path.rglob("*") if _is_supported(p))
    for candidate in candidates:
        if not candidate.is_file() or not _is_supported(candidate):
            continue
        yield IngestItem(path=candidate, source_type=_detect_source_type(candidate))


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


def _batched(iterable: Iterable[IngestItem], size: int) -> Iterator[list[IngestItem]]:
    iterator = iter(iterable)
    while True:
        batch = list(islice(iterator, size))
        if not batch:
            return
        yield batch


def _apply_default_metadata(overrides: dict[str, object]) -> dict[str, object]:
    """Ensure CLI ingests provide baseline metadata for discovery."""

    enriched = dict(overrides)
    enriched.setdefault("collection", DEFAULT_COLLECTION)
    if "author" not in enriched and "authors" not in enriched:
        enriched["author"] = DEFAULT_AUTHOR
    return enriched


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
    enrich_document_task = cast(Any, worker_tasks.enrich_document)
    for doc_id in document_ids:
        try:
            async_result = enrich_document_task.delay(doc_id)
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
    batch: list[IngestItem],
    overrides: dict[str, object],
    post_batch_steps: set[str] | None = None,
    *,
    dependencies: PipelineDependencies | None = None,
) -> list[str]:
    engine = get_engine()
    dependency_bundle = dependencies or PipelineDependencies(settings=get_settings())
    document_ids: list[str] = []
    with Session(engine) as session:
        for item in batch:
            frontmatter = dict(overrides)
            if item.is_remote:
                document = run_pipeline_for_url(
                    session,
                    cast(str, item.url),
                    source_type=item.source_type,
                    frontmatter=frontmatter,
                    dependencies=dependency_bundle,
                )
            else:
                document = run_pipeline_for_file(
                    session,
                    cast(Path, item.path),
                    frontmatter,
                    dependencies=dependency_bundle,
                )
            document_ids.append(document.id)
        if post_batch_steps:
            _run_post_batch_operations(session, document_ids, post_batch_steps)
    return document_ids


def _queue_batch_via_worker(
    batch: list[IngestItem], overrides: dict[str, object]
) -> list[str]:
    task_ids: list[str] = []
    process_file_task = cast(Any, worker_tasks.process_file)
    process_url_task = cast(Any, worker_tasks.process_url)
    for item in batch:
        frontmatter = dict(overrides)
        if item.is_remote:
            async_result = process_url_task.delay(
                str(uuid4()),
                cast(str, item.url),
                item.source_type,
                frontmatter,
            )
        else:
            async_result = process_file_task.delay(
                str(uuid4()), str(cast(Path, item.path)), frontmatter
            )
        task_ids.append(async_result.id if hasattr(async_result, "id") else "queued")
    return task_ids


@click.command()
@click.argument("source", type=str)
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
    source: str,
    *,
    mode: str,
    batch_size: int,
    dry_run: bool,
    metadata_overrides: tuple[str, ...],
    post_batch_steps: tuple[str, ...],
) -> None:
    """Queue every supported source (path or URL) for ingestion."""

    overrides = _apply_default_metadata(
        _parse_metadata_overrides(metadata_overrides)
    )
    try:
        items = _discover_items([source])
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    normalized_post_batch = _parse_post_batch_steps(post_batch_steps)
    if not items:
        click.echo("No supported files found.")
        log_workflow_event(
            "cli.ingest.empty",
            workflow="cli.ingest_folder",
            source=source,
        )
        return

    click.echo(f"Discovered {len(items)} supported file(s) from {source}.")
    log_workflow_event(
        "cli.ingest.started",
        workflow="cli.ingest_folder",
        source=source,
        mode=mode,
        dry_run=dry_run,
        batch_size=batch_size,
        item_count=len(items),
    )
    for batch_number, batch in enumerate(_batched(items, batch_size), start=1):
        click.echo(f"Batch {batch_number}: {len(batch)} item(s).")
        log_workflow_event(
            "cli.ingest.batch",
            workflow="cli.ingest_folder",
            source=source,
            batch_number=batch_number,
            batch_size=len(batch),
        )
        for item in batch:
            click.echo(f" - [{item.source_type}] {item.label}")

        if dry_run:
            click.echo("Dry-run enabled; skipping ingestion.")
            log_workflow_event(
                "cli.ingest.dry_run",
                workflow="cli.ingest_folder",
                source=source,
                batch_number=batch_number,
            )
            continue

        if mode.lower() == "api":
            document_ids = _ingest_batch_via_api(
                batch, overrides, normalized_post_batch
            )
            for item, doc_id in zip(batch, document_ids):
                click.echo(f"   Processed {item.label} → document {doc_id}")
                log_workflow_event(
                    "cli.ingest.processed",
                    workflow="cli.ingest_folder",
                    source=source,
                    backend="api",
                    target=item.label,
                    document_id=doc_id,
                )
        else:
            if normalized_post_batch:
                click.echo("   Post-batch steps require API mode; skipping.")
            task_ids = _queue_batch_via_worker(batch, overrides)
            for item, task_id in zip(batch, task_ids):
                click.echo(f"   Queued {item.label} → task {task_id}")
                log_workflow_event(
                    "cli.ingest.queued",
                    workflow="cli.ingest_folder",
                    source=source,
                    backend="worker",
                    target=item.label,
                    task_id=task_id,
                )

    log_workflow_event(
        "cli.ingest.completed",
        workflow="cli.ingest_folder",
        source=source,
        mode=mode,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    ingest_folder()
