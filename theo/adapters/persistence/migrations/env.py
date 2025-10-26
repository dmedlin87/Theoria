"""Alembic environment configuration for Theo persistence models."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from theo.adapters.persistence import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _configure_url_from_env() -> None:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:  # pragma: no cover - Alembic entry point
    """Run migrations in 'offline' mode."""

    _configure_url_from_env()
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError(
            "DATABASE_URL must be set for offline Alembic migrations."
        )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:  # pragma: no cover - Alembic entry point
    """Run migrations in 'online' mode."""

    _configure_url_from_env()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():  # pragma: no cover - Alembic entry point
    run_migrations_offline()
else:  # pragma: no cover - Alembic entry point
    run_migrations_online()
