"""Theo command line interface entry point."""

from __future__ import annotations

import sys
import logging
from typing import NoReturn

import click

from theo.commands import register_commands
from theo.commands.embedding_rebuild import rebuild_embeddings_cmd


_LOGGER = logging.getLogger(__name__)


def _handle_cli_error(exc: Exception) -> NoReturn:
    """Handle CLI exceptions with consistent error reporting and exit codes."""
    
    # Log the full exception for debugging
    _LOGGER.error("CLI command failed: %s", exc, exc_info=True)
    
    # Show user-friendly error message
    if isinstance(exc, click.ClickException):
        # ClickException already has good user messaging
        exc.show()
        sys.exit(exc.exit_code)
    elif isinstance(exc, KeyboardInterrupt):
        click.echo("\nOperation cancelled by user.", err=True)
        sys.exit(130)  # Standard exit code for SIGINT
    elif isinstance(exc, (OSError, IOError)):
        click.echo(f"Error: File system operation failed: {exc}", err=True)
        sys.exit(1)
    elif isinstance(exc, ImportError):
        click.echo(f"Error: Missing required dependency: {exc}", err=True)
        sys.exit(1)
    else:
        # Generic error handling for unexpected exceptions
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@click.group()
def cli() -> None:
    """Theo CLI entry point with robust error handling."""
    pass


# Register all commands
register_commands(cli)


__all__ = ["cli", "rebuild_embeddings_cmd"]


def main() -> None:
    """Main CLI entry point with comprehensive error handling."""
    try:
        cli()
    except Exception as exc:
        _handle_cli_error(exc)


if __name__ == "__main__":
    main()
