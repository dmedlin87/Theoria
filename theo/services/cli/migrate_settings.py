"""CLI to migrate plaintext settings into encrypted storage."""

from __future__ import annotations

import click
from sqlalchemy.orm import Session

from theo.application.facades.secret_migration import migrate_secret_settings
from theo.application.facades.settings import get_settings_cipher
from theo.services.bootstrap import resolve_application


APPLICATION_CONTAINER, _ADAPTER_REGISTRY = resolve_application()


def get_engine():  # pragma: no cover - transitional wiring helper
    return _ADAPTER_REGISTRY.resolve("engine")


@click.command()
@click.option("--dry-run", is_flag=True, help="Preview keys that would be migrated")
def main(dry_run: bool) -> None:
    """Scan the settings store and re-encrypt any plaintext secrets."""

    if get_settings_cipher() is None:
        raise click.ClickException(
            "SETTINGS_SECRET_KEY must be configured before running the migration"
        )

    engine = get_engine()
    with Session(engine) as session:
        migrated = migrate_secret_settings(session, dry_run=dry_run)
        if not migrated:
            click.echo("No plaintext settings found.")
            return
        if dry_run:
            click.echo("The following settings would be re-encrypted:")
        else:
            click.echo("Re-encrypted the following settings:")
        for key in migrated:
            click.echo(f" - {key}")


if __name__ == "__main__":
    main()
