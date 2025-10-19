from __future__ import annotations

import itertools
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import click
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import Document, Passage
from theo.services.api.app.ingest.embeddings import (
    clear_embedding_cache,
    get_embedding_service,
)
from theo.services.api.app.ingest.sanitizer import sanitize_passage_text
from theo.services.bootstrap import resolve_application


@click.group()
def cli() -> None:
    """Theo CLI entry point."""


def _batched(iterator: Iterator, size: int) -> Iterator[list]:
    while True:
        batch = list(itertools.islice(iterator, size))
        if not batch:
            break
        yield batch


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


def _commit_with_retry(session: Session, *, max_attempts: int = 3, backoff: float = 0.5) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            session.commit()
        except SQLAlchemyError as exc:  # pragma: no cover - defensive retry path
            session.rollback()
            if attempt == max_attempts:
                raise click.ClickException(
                    f"Database commit failed after {attempt} attempt(s): {exc}"
                ) from exc
            time.sleep(backoff * attempt)
        else:
            return


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
        engine = registry.resolve("engine")
    except Exception as exc:  # pragma: no cover - defensive
        raise click.ClickException(f"Failed to resolve application: {exc}") from exc

    batch_size = 64 if fast else 128
    embedding_service = get_embedding_service()
    if no_cache:
        clear_embedding_cache()

    start = time.perf_counter()
    processed = 0

    normalized_changed_since = _normalise_timestamp(changed_since)
    ids: list[str] | None = None
    if ids_file is not None:
        ids = _load_ids(ids_file)
        if not ids:
            click.echo("No passage IDs were found in the provided file.")
            return

    checkpoint_state: dict[str, object] = {}
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

    where_clause = Passage.embedding.is_(None) if fast else None

    with Session(engine) as session:
        filters: list = []
        join_document = False
        if where_clause is not None:
            filters.append(where_clause)
        if normalized_changed_since is not None:
            join_document = True
            filters.append(Document.updated_at >= normalized_changed_since)
        if ids:
            filters.append(Passage.id.in_(ids))

        count_stmt = select(func.count(Passage.id)).select_from(Passage)
        if join_document:
            count_stmt = count_stmt.join(Document)
        for criterion in filters:
            count_stmt = count_stmt.where(criterion)
        total = session.execute(count_stmt).scalar_one()

        if total == 0:
            click.echo("No passages require embedding updates.")
            return

        if ids:
            expected_ids = set(
                session.execute(
                    select(Passage.id).where(Passage.id.in_(ids))
                ).scalars()
            )
            missing_ids = [item for item in ids if item not in expected_ids]
            if missing_ids:
                click.echo(
                    f"{len(missing_ids)} passage ID(s) were not found and will be skipped."
                )

        click.echo(
            f"Rebuilding embeddings for {total} passage(s) using batch size {batch_size}."
        )

        stmt = (
            select(Passage)
            .order_by(Passage.id)
            .execution_options(stream_results=True, yield_per=batch_size)
        )
        if where_clause is not None:
            stmt = stmt.where(where_clause)
        if join_document:
            stmt = stmt.join(Document)
        for criterion in filters:
            if criterion is where_clause:
                continue  # already applied
            stmt = stmt.where(criterion)

        stream = session.execute(stmt).scalars()
        if skip_count:
            stream = itertools.islice(stream, skip_count, None)
            processed = min(skip_count, total)

        metadata = {
            "fast": fast,
            "changed_since": normalized_changed_since.isoformat()
            if normalized_changed_since
            else None,
            "ids_file": str(ids_file) if ids_file else None,
            "ids_count": len(ids) if ids else None,
            "resume": resume,
        }

        for batch_index, batch in enumerate(_batched(stream, batch_size), start=1):
            if not batch:
                continue
            texts = [sanitize_passage_text(item.text or "") for item in batch]
            batch_start = time.perf_counter()
            try:
                vectors = embedding_service.embed(texts, batch_size=batch_size)
            except Exception as exc:  # pragma: no cover - defensive
                raise click.ClickException(f"Embedding generation failed: {exc}") from exc

            if len(vectors) != len(batch):
                raise click.ClickException("Embedding backend returned mismatched batch size")

            payload = [
                {"id": passage.id, "embedding": list(vector)}
                for passage, vector in zip(batch, vectors)
            ]

            session.bulk_update_mappings(Passage, payload)
            _commit_with_retry(session)
            processed += len(batch)
            batch_duration = time.perf_counter() - batch_start
            rate = batch_duration / len(batch)
            click.echo(
                f"Batch {batch_index}: updated {processed}/{total} passages "
                f"in {batch_duration:.2f}s ({rate:.3f}s/pass)"
            )

            if checkpoint_file is not None:
                last_id = batch[-1].id
                _write_checkpoint(
                    checkpoint_file,
                    processed=processed,
                    total=total,
                    last_id=last_id,
                    metadata=metadata,
                )
        if checkpoint_file is not None:
            click.echo(f"Checkpoint written to {checkpoint_file}")

    duration = time.perf_counter() - start
    click.echo(
        f"Completed embedding rebuild for {processed} passage(s) in {duration:.2f}s."
    )


if __name__ == "__main__":
    cli()
