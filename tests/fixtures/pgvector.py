from __future__ import annotations

import contextlib
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Iterator
from urllib.parse import ParseResult, urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

try:  # pragma: no cover - optional dependency in lightweight environments
    from testcontainers.postgres import PostgresContainer
except ModuleNotFoundError as exc:  # pragma: no cover - surfaces in light CI runs
    PostgresContainer = None  # type: ignore[assignment]
    _TESTCONTAINERS_IMPORT_ERROR: ModuleNotFoundError | None = exc
else:
    _TESTCONTAINERS_IMPORT_ERROR = None

DEFAULT_IMAGE = os.environ.get("PYTEST_PGVECTOR_IMAGE", "pgvector/pgvector:pg15")
_VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class PGVectorClone:
    """Description of a cloned database derived from the pgvector template."""

    name: str
    url: str


@dataclass
class PGVectorDatabase:
    """Manage a pgvector-enabled Postgres Testcontainer for integration tests."""

    container: PostgresContainer
    raw_url: str
    url: str
    admin_url: str
    database: str
    user: str
    password: str
    host: str
    port: int
    image: str
    _clones: list[PGVectorClone] = field(default_factory=list)

    def create_engine(self, *, database: str | None = None, **kwargs: object) -> Engine:
        """Return a SQLAlchemy engine bound to the template or a cloned database."""

        target = self.url if database is None else _swap_database(self.url, database)
        engine_kwargs = {"future": True}
        engine_kwargs.update(kwargs)
        return create_engine(target, **engine_kwargs)

    def clone_database(self, prefix: str = "pytest") -> PGVectorClone:
        """Create a copy-on-write database derived from the seeded template."""

        if not _VALID_IDENTIFIER.match(prefix):
            raise ValueError(
                "pgvector clone prefixes must be alphanumeric with underscores, "
                f"got {prefix!r}",
            )

        name = f"{prefix}_{uuid.uuid4().hex[:8]}"
        self._create_database(name)
        clone = PGVectorClone(name=name, url=_swap_database(self.url, name))
        self._clones.append(clone)
        return clone

    def drop_clone(self, clone: PGVectorClone | str) -> None:
        """Drop a previously created clone, ignoring failures during shutdown."""

        name = clone.name if isinstance(clone, PGVectorClone) else clone
        with contextlib.suppress(Exception):
            self._drop_database(name)
        self._clones = [existing for existing in self._clones if existing.name != name]

    def close(self) -> None:
        """Drop any clones and stop the underlying container."""

        for clone in reversed(self._clones):
            with contextlib.suppress(Exception):
                self._drop_database(clone.name)
        self._clones.clear()
        with contextlib.suppress(Exception):
            self.container.stop()

    def _create_database(self, name: str) -> None:
        if not _VALID_IDENTIFIER.match(name):
            raise ValueError(f"Invalid Postgres database identifier: {name!r}")
        statement = text(f'CREATE DATABASE "{name}" TEMPLATE "{self.database}"')
        self._run_admin(statement)

    def _drop_database(self, name: str) -> None:
        if not _VALID_IDENTIFIER.match(name):
            return
        statement = text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        self._run_admin(statement)

    def _run_admin(self, statement) -> None:
        engine = create_engine(
            self.admin_url,
            future=True,
            isolation_level="AUTOCOMMIT",
        )
        try:
            with engine.connect() as connection:
                connection.execute(statement)
        finally:
            engine.dispose()


@dataclass(frozen=True)
class _ConnectionDetails:
    database: str
    host: str
    port: int
    user: str
    password: str


def _normalise_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _swap_database(url: str, database: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{database}"))


def _parse_connection_details(url: str) -> _ConnectionDetails:
    parsed: ParseResult = urlparse(url)
    database = parsed.path.lstrip("/") or "postgres"
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username or "postgres"
    password = parsed.password or "postgres"
    return _ConnectionDetails(
        database=database,
        host=host,
        port=port,
        user=user,
        password=password,
    )


def _prepare_template(url: str) -> None:
    from theo.adapters.persistence import Base
    from theo.infrastructure.api.app.db.run_sql_migrations import run_sql_migrations
    from theo.infrastructure.api.app.db.seeds import seed_reference_data

    engine = create_engine(url, future=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        Base.metadata.create_all(bind=engine)
        run_sql_migrations(engine)
        with Session(engine) as session:
            seed_reference_data(session)
            session.commit()
    finally:
        engine.dispose()


@contextlib.contextmanager
def provision_pgvector_database(
    *, image: str | None = None
) -> Iterator[PGVectorDatabase]:
    """Provision a pgvector-enabled Postgres database backed by Testcontainers."""

    if PostgresContainer is None:
        assert _TESTCONTAINERS_IMPORT_ERROR is not None
        raise _TESTCONTAINERS_IMPORT_ERROR

    selected_image = image or DEFAULT_IMAGE
    container = PostgresContainer(image=selected_image)
    container.with_env("POSTGRES_DB", "theo_template")
    container.with_env("POSTGRES_USER", "postgres")
    container.with_env("POSTGRES_PASSWORD", "postgres")

    container.start()
    database: PGVectorDatabase | None = None
    try:
        raw_url = container.get_connection_url()
        url = _normalise_database_url(raw_url)
        _prepare_template(url)
        details = _parse_connection_details(url)
        admin_url = _swap_database(url, "postgres")
        database = PGVectorDatabase(
            container=container,
            raw_url=raw_url,
            url=url,
            admin_url=admin_url,
            database=details.database,
            user=details.user,
            password=details.password,
            host=details.host,
            port=details.port,
            image=selected_image,
        )
        yield database
    finally:
        if database is not None:
            database.close()
        else:
            with contextlib.suppress(Exception):
                container.stop()


__all__ = [
    "PGVectorClone",
    "PGVectorDatabase",
    "provision_pgvector_database",
]
