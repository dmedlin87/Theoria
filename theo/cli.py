"""Theo command line interface entry point."""

from __future__ import annotations

import click

from theo.commands import register_commands
from theo.commands.embedding_rebuild import rebuild_embeddings_cmd


@click.group()
def cli() -> None:
    """Theo CLI entry point."""


register_commands(cli)

__all__ = ["cli", "rebuild_embeddings_cmd"]


if __name__ == "__main__":
    cli()
