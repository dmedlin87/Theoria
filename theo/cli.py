from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import click
from theo.application.embeddings import (
    EmbeddingRebuildError,
    EmbeddingRebuildOptions,
    EmbeddingRebuildProgress,
    EmbeddingRebuildResult,
    EmbeddingRebuildService,
    EmbeddingRebuildStart,
)
from theo.services.bootstrap import resolve_application


@click.group()
def cli() -> None:
    """Theo CLI entry point."""
def _normalise_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _load_ids(path: Path) -> list[str]:
    ids = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    ids = [item for item in ids if item]
    # Preserve ordering while removing duplicates
    seen: set[str] = set()
    deduped: list[str] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _read_checkpoint(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _write_checkpoint(
    path: Path,
    *,
    processed: int,
    total: int,
    last_id: str | None,
    metadata: dict[str, object],
) -> None:
    payload = {
        "processed": processed,
        "total": total,
        "last_id": last_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@cli.command("rebuild_embeddings")
@click.option("--fast", is_flag=True, help="Skip slow checks where possible.")
@click.option("--no-cache", is_flag=True, help="Ignore local caches.")
@click.option(
    "--changed-since",
    type=click.DateTime(
        formats=[
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
        ]
    ),
    help="Only rebuild passages whose parent documents changed at or after this timestamp (ISO format).",
)
@click.option(
    "--ids-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a file containing passage IDs (one per line) to rebuild.",
)
@click.option(
    "--checkpoint-file",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Persist progress to this file so long-running runs can resume later.",
)
@click.option(
    "--resume/--fresh",
    default=False,
    help="Resume from an existing checkpoint file instead of starting from scratch.",
)
def rebuild_embeddings_cmd(
    fast: bool,
    no_cache: bool,
    changed_since: datetime | None,
    ids_file: Path | None,
    checkpoint_file: Path | None,
    resume: bool,
) -> None:
    """Rebuild vector store from normalized artifacts."""

    try:
        _, registry = resolve_application()
        service = registry.resolve("embedding_rebuild_service")
    except Exception as exc:  # pragma: no cover - defensive
        raise click.ClickException(f"Failed to resolve application: {exc}") from exc

    if not isinstance(service, EmbeddingRebuildService):
        raise click.ClickException("Embedding rebuild service unavailable")

    batch_size = 64 if fast else 128

    normalized_changed_since = _normalise_timestamp(changed_since)
    ids: Sequence[str] | None = None
    if ids_file is not None:
        ids = _load_ids(ids_file)
        if not ids:
            click.echo("No passage IDs were found in the provided file.")
            return

    skip_count = 0
    if checkpoint_file is not None:
        if resume:
            checkpoint_state = _read_checkpoint(checkpoint_file)
            skip_count = int(checkpoint_state.get("processed", 0)) if checkpoint_state else 0
            if skip_count:
                click.echo(
                    f"Resuming from checkpoint at {checkpoint_file} "
                    f"(already processed {skip_count} passage(s))."
                )
        else:
            try:
                checkpoint_file.unlink()
            except FileNotFoundError:
                pass

    metadata = {
        "fast": fast,
        "changed_since": normalized_changed_since.isoformat()
        if normalized_changed_since
        else None,
        "ids_file": str(ids_file) if ids_file else None,
        "ids_count": len(ids) if ids else None,
        "resume": resume,
    }

    checkpoint_written = False

    def _on_start(start: EmbeddingRebuildStart) -> None:
        if start.missing_ids:
            click.echo(
                f"{len(start.missing_ids)} passage ID(s) were not found and will be skipped."
            )
        if start.total == 0:
            click.echo("No passages require embedding updates.")
        else:
            click.echo(
                f"Rebuilding embeddings for {start.total} passage(s) "
                f"using batch size {batch_size}."
            )

    def _on_progress(progress: EmbeddingRebuildProgress) -> None:
        nonlocal checkpoint_written
        click.echo(
            f"Batch {progress.batch_index}: updated {progress.state.processed}/"
            f"{progress.state.total} passages in {progress.batch_duration:.2f}s "
            f"({progress.rate_per_passage:.3f}s/pass)"
        )
        if checkpoint_file is not None:
            _write_checkpoint(
                checkpoint_file,
                processed=progress.state.processed,
                total=progress.state.total,
                last_id=progress.state.last_id,
                metadata=dict(progress.state.metadata),
            )
            checkpoint_written = True

    options = EmbeddingRebuildOptions(
        fast=fast,
        batch_size=batch_size,
        changed_since=normalized_changed_since,
        ids=ids,
        skip_count=skip_count,
        metadata=metadata,
        clear_cache=no_cache,
    )

    try:
        result: EmbeddingRebuildResult = service.rebuild_embeddings(
            options,
            on_start=_on_start,
            on_progress=_on_progress,
        )
    except EmbeddingRebuildError as exc:
        raise click.ClickException(str(exc)) from exc

    if result.total == 0:
        return

    if checkpoint_file is not None and checkpoint_written:
        click.echo(f"Checkpoint written to {checkpoint_file}")

    click.echo(
        f"Completed embedding rebuild for {result.processed} passage(s) "
        f"in {result.duration:.2f}s."
    )


if __name__ == "__main__":
    cli()
