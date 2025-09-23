"""Bulk ingest CLI stub."""

from pathlib import Path

import click


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def ingest_folder(path: Path):
    """Queue every supported file in PATH for ingestion."""

    click.echo(f"Ingesting folder: {path}")


if __name__ == "__main__":
    ingest_folder()
