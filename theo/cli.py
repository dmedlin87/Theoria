from __future__ import annotations

import itertools
import time

import click
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import Passage
from theo.services.api.app.ingest.embeddings import (
    clear_embedding_cache,
    get_embedding_service,
)
from theo.services.api.app.ingest.sanitizer import sanitize_passage_text
from theo.services.bootstrap import resolve_application


@click.group()
def cli() -> None:
    """Theo CLI entry point."""


def _batched(iterator, size: int):
    while True:
        batch = list(itertools.islice(iterator, size))
        if not batch:
            break
        yield batch


@cli.command("rebuild_embeddings")
@click.option("--fast", is_flag=True, help="Skip slow checks where possible.")
@click.option("--no-cache", is_flag=True, help="Ignore local caches.")
def rebuild_embeddings_cmd(fast: bool, no_cache: bool) -> None:
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

    where_clause = Passage.embedding.is_(None) if fast else None

    with Session(engine) as session:
        count_stmt = select(func.count()).select_from(Passage)
        if where_clause is not None:
            count_stmt = count_stmt.where(where_clause)
        total = session.execute(count_stmt).scalar_one()

        if total == 0:
            click.echo("No passages require embedding updates.")
            return

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

        stream = session.execute(stmt).scalars()

        for batch in _batched(stream, batch_size):
            texts = [sanitize_passage_text(item.text or "") for item in batch]
            try:
                vectors = embedding_service.embed(texts, batch_size=batch_size)
            except Exception as exc:  # pragma: no cover - defensive
                raise click.ClickException(f"Embedding generation failed: {exc}") from exc

            if len(vectors) != len(batch):
                raise click.ClickException("Embedding backend returned mismatched batch size")

            for passage, vector in zip(batch, vectors):
                passage.embedding = list(vector)

            session.commit()
            processed += len(batch)
            click.echo(f"Updated {processed}/{total} passages", nl=False)
            click.echo("\r", nl=False)

    duration = time.perf_counter() - start
    click.echo(
        f"Completed embedding rebuild for {processed} passage(s) in {duration:.2f}s."
    )


if __name__ == "__main__":
    cli()
