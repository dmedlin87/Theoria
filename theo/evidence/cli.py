"""Command line interface for the evidence toolkit."""

from __future__ import annotations

import json
from pathlib import Path

import click

from .dossier import EvidenceDossier
from .indexer import EvidenceIndexer
from .promoter import EvidencePromoter
from .validator import EvidenceValidator


@click.group()
def cli() -> None:
    """Evidence management commands."""


@cli.command("validate")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.option("--all", "validate_all", is_flag=True, help="Validate every file in a directory")
@click.option("--base-path", type=click.Path(path_type=Path), default=Path.cwd())
def validate_command(paths: tuple[Path, ...], validate_all: bool, base_path: Path) -> None:
    """Validate evidence payloads and emit normalized JSON."""

    validator = EvidenceValidator(base_path=base_path)
    if validate_all:
        if not paths:
            raise click.BadOptionUsage("--all", "Provide a directory to validate.")
        collection = validator.validate_all(paths[0])
    else:
        if not paths:
            raise click.UsageError("Provide at least one evidence file to validate.")
        collection = validator.validate_many(paths)
    click.echo(json.dumps([record.model_dump(mode="json") for record in collection.records], indent=2))


@cli.command("index")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.option("--sqlite", "sqlite_path", required=True, type=click.Path(path_type=Path))
@click.option("--base-path", type=click.Path(path_type=Path), default=Path.cwd())
def index_command(paths: tuple[Path, ...], sqlite_path: Path, base_path: Path) -> None:
    """Build a SQLite index from evidence payloads."""

    if not paths:
        raise click.UsageError("Provide at least one evidence source file.")
    validator = EvidenceValidator(base_path=base_path)
    indexer = EvidenceIndexer(validator)
    collection = indexer.build_sqlite(paths, sqlite_path=sqlite_path)
    click.echo(f"Indexed {len(collection.records)} records into {sqlite_path}")


@cli.command("promote")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.option("--output", "output_path", required=True, type=click.Path(path_type=Path))
@click.option("--sqlite", "sqlite_path", type=click.Path(path_type=Path))
@click.option("--base-path", type=click.Path(path_type=Path), default=Path.cwd())
def promote_command(
    paths: tuple[Path, ...],
    output_path: Path,
    sqlite_path: Path | None,
    base_path: Path,
) -> None:
    """Validate, normalize, and publish curated artifacts."""

    if not paths:
        raise click.UsageError("Provide at least one evidence file to promote.")
    validator = EvidenceValidator(base_path=base_path)
    promoter = EvidencePromoter(validator=validator)
    collection = promoter.promote(paths, destination=output_path, sqlite_path=sqlite_path)
    click.echo(f"Promoted {len(collection.records)} records to {output_path}")
    if sqlite_path:
        click.echo(f"SQLite index available at {sqlite_path}")


@cli.command("dossier")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.option("--graph", "render_graph", is_flag=True, help="Emit a JSON graph of OSIS to evidence")
@click.option("--base-path", type=click.Path(path_type=Path), default=Path.cwd())
def dossier_command(paths: tuple[Path, ...], render_graph: bool, base_path: Path) -> None:
    """Generate analytical dossiers for evidence collections."""

    if not paths:
        raise click.UsageError("Provide at least one evidence file.")
    validator = EvidenceValidator(base_path=base_path)
    dossier = EvidenceDossier(validator)
    if render_graph:
        graph = dossier.build_graph(paths)
        click.echo(json.dumps(graph, indent=2))
    else:
        collection = validator.validate_many(paths)
        click.echo(json.dumps([record.model_dump(mode="json") for record in collection.records], indent=2))


@cli.command("query")
@click.argument("sqlite_path", type=click.Path(path_type=Path))
@click.option("--osis", type=str)
@click.option("--tag", type=str)
def query_command(sqlite_path: Path, osis: str | None, tag: str | None) -> None:
    """Query a SQLite index for specific evidence."""

    indexer = EvidenceIndexer()
    results = indexer.query(sqlite_path, osis=osis, tag=tag)
    click.echo(json.dumps([record.model_dump(mode="json") for record in results], indent=2))


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    cli()


__all__ = ["cli"]
