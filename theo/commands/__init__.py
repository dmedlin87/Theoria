"""Command modules for Theo's CLI."""

from __future__ import annotations

import click

from . import database_ops, embedding_rebuild, import_export

__all__ = ["register_commands", "embedding_rebuild", "database_ops", "import_export"]


def register_commands(cli: click.Group) -> None:
    """Register all CLI commands with the provided group."""

    embedding_rebuild.register_commands(cli)
    database_ops.register_commands(cli)
    import_export.register_commands(cli)
