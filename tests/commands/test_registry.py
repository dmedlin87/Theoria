from __future__ import annotations

import click

from theo.commands import database_ops, import_export, register_commands
from theo.commands.embedding_rebuild import rebuild_embeddings_cmd


def test_register_commands_adds_embedding_command() -> None:
    group = click.Group()
    register_commands(group)
    assert "rebuild_embeddings" in group.commands
    assert group.get_command(None, "rebuild_embeddings") is rebuild_embeddings_cmd


def test_database_ops_register_commands_noop() -> None:
    group = click.Group()
    database_ops.register_commands(group)
    assert group.commands == {}


def test_import_export_register_commands_noop() -> None:
    group = click.Group()
    import_export.register_commands(group)
    assert group.commands == {}
