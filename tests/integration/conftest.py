from __future__ import annotations

from collections.abc import Generator, Iterator

import pytest

from tests.integration._stubs import install_celery_stub, install_sklearn_stub

try:  # pragma: no cover - optional SQLAlchemy dependency
    from sqlalchemy import create_engine
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool
except ModuleNotFoundError:  # pragma: no cover - allow lightweight environments
    create_engine = None  # type: ignore[assignment]
    Engine = Session = object  # type: ignore[assignment]
    sessionmaker = StaticPool = None  # type: ignore[assignment]
    Base = None  # type: ignore[assignment]
    run_sql_migrations = None  # type: ignore[assignment]
else:
    from theo.adapters.persistence import Base

    try:  # pragma: no cover - migrations optional in light environments
        from theo.services.api.app.db.run_sql_migrations import run_sql_migrations
    except ModuleNotFoundError:  # pragma: no cover - lightweight test runs
        run_sql_migrations = None  # type: ignore[assignment]


install_sklearn_stub()
install_celery_stub()


@pytest.fixture(scope="session")
def sqlite_memory_engine() -> Iterator[Engine]:
    """Create the in-memory SQLite engine once per session."""

    if create_engine is None or Base is None or StaticPool is None:
        pytest.skip("sqlalchemy not installed")

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    if run_sql_migrations is not None:
        run_sql_migrations(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def sqlite_session(sqlite_memory_engine: Engine) -> Generator[Session, None, None]:
    """Wrap each test in a transaction that is rolled back afterwards."""

    if sessionmaker is None:
        pytest.skip("sqlalchemy not installed")

    connection = sqlite_memory_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def baseline_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Provide consistent configuration for integration scenarios."""

    from theo.application.facades import database as database_module
    from theo.application.facades.settings import get_settings
    from theo.platform.application import resolve_application
    from theo.services.api.app.db import query_optimizations
    from theo.services.api.app.routes import documents as documents_route

    monkeypatch.setenv("SETTINGS_SECRET_KEY", "integration-secret")
    monkeypatch.setenv("THEO_API_KEYS", '["pytest-default-key"]')
    monkeypatch.setenv("THEO_ALLOW_INSECURE_STARTUP", "1")
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "test")
    monkeypatch.setenv("THEO_FORCE_EMBEDDING_FALLBACK", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(query_optimizations, "record_histogram", lambda *_, **__: None)
    monkeypatch.setattr(query_optimizations, "record_counter", lambda *_, **__: None)
    try:
        yield
    finally:
        get_settings.cache_clear()
        reset_reranker = getattr(documents_route, "reset_reranker_cache", None)
        if callable(reset_reranker):
            reset_reranker()
        resolve_application.cache_clear()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]
