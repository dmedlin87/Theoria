"""CLI for importing OSIS commentary sources."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import click
from sqlalchemy.orm import Session

from theo.application.facades.database import Base, configure_engine
from theo.services.bootstrap import resolve_application

from ..api.app.ingest.pipeline import PipelineDependencies, import_osis_commentary


APPLICATION_CONTAINER, _ADAPTER_REGISTRY = resolve_application()


def get_settings():  # pragma: no cover - transitional wiring helper
    return _ADAPTER_REGISTRY.resolve("settings")


def get_engine():  # pragma: no cover - transitional wiring helper
    return _ADAPTER_REGISTRY.resolve("engine")


@click.command()
@click.argument("osis_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--source",
    type=str,
    default=None,
    help="Optional source label for the commentary excerpts.",
)
@click.option(
    "--perspective",
    type=str,
    default=None,
    help="Perspective applied to imported excerpts (defaults to neutral).",
)
@click.option(
    "--tag",
    "tags",
    multiple=True,
    help="Tag to assign to each imported excerpt (repeatable).",
)
@click.option(
    "--database",
    type=str,
    default=None,
    help="Override database URL (defaults to configured engine).",
)
def ingest_osis(
    osis_path: Path,
    source: str | None,
    perspective: str | None,
    tags: Sequence[str],
    database: str | None,
) -> None:
    """Import OSIS/XML commentaries into the seed catalogue."""

    if database:
        configure_engine(database)

    engine = get_engine()
    settings = get_settings()

    # Ensure schema is present when pointing at a fresh SQLite database.
    if database:
        Base.metadata.create_all(engine)

    frontmatter: dict[str, object] = {}
    if source:
        frontmatter["source"] = source
    if perspective:
        frontmatter["perspective"] = perspective
    if tags:
        frontmatter["tags"] = list(tags)

    dependencies = PipelineDependencies(settings=settings)

    with Session(engine) as session:
        result = import_osis_commentary(
            session,
            osis_path,
            frontmatter=frontmatter or None,
            dependencies=dependencies,
        )

    click.echo(
        "Imported {inserted} new commentary excerpts, updated {updated}, "
        "skipped {skipped}.".format(
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
        )
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    ingest_osis()
