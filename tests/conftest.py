from __future__ import annotations

import asyncio
import contextlib
import importlib
import inspect
import os
import sys
from collections.abc import Generator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - imported only for type checking
    from theo.adapters import AdapterRegistry
    from theo.application import ApplicationContainer
    from tests.fixtures import RegressionDataFactory

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from tests.factories.application import isolated_application_container

try:  # pragma: no cover - optional dependency in local test harness
    import pytest_cov  # type: ignore  # noqa: F401

    _HAS_PYTEST_COV = True
except ModuleNotFoundError:  # pragma: no cover - executed when plugin is missing
    _HAS_PYTEST_COV = False


def _register_randomly_plugin(pluginmanager: pytest.PluginManager) -> bool:
    """Ensure pytest-randomly is registered when available."""

    if pluginmanager.hasplugin("randomly"):
        return True

    try:
        plugin_module = importlib.import_module("pytest_randomly.plugin")
    except ModuleNotFoundError:
        return False

    pluginmanager.register(plugin_module, "pytest_randomly")
    return True


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register optional CLI flags and shim coverage arguments when needed."""

    if not _HAS_PYTEST_COV:
        group = parser.getgroup("cov", "coverage reporting (stub)")
        group.addoption(
            "--cov",
            action="append",
            default=[],
            dest="cov_source",
            metavar="PATH",
            help="Stub option allowing tests to run without pytest-cov installed.",
        )
        group.addoption(
            "--cov-report",
            action="append",
            default=[],
            dest="cov_report",
            metavar="TYPE",
            help="Stub option allowing tests to run without pytest-cov installed.",
        )
        group.addoption(
            "--cov-fail-under",
            action="store",
            default=None,
            dest="cov_fail_under",
            type=float,
            help="Stub option allowing tests to run without pytest-cov installed.",
        )

    parser.addoption(
        "--pgvector",
        action="store_true",
        default=False,
        dest="pgvector",
        help="Enable tests marked with @pytest.mark.pgvector (starts a Postgres+pgvector Testcontainer).",
    )
    parser.addoption(
        "--use-pgvector",
        action="store_true",
        default=False,
        dest="pgvector",
        help="Deprecated alias for --pgvector.",
    )
    parser.addoption(
        "--schema",
        action="store_true",
        default=False,
        dest="schema",
        help="Allow database schema migrations required by @pytest.mark.schema tests.",
    )
    parser.addoption(
        "--contract",
        action="store_true",
        default=False,
        dest="contract",
        help="Run contract suites marked with @pytest.mark.contract.",
    )
    parser.addoption(
        "--gpu",
        action="store_true",
        default=False,
        dest="gpu",
        help="Allow GPU-dependent tests marked with @pytest.mark.gpu.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers used throughout the test suite."""

    if _register_randomly_plugin(config.pluginmanager):
        config.option.randomly_seed = 1337

    config.addinivalue_line(
        "markers",
        "asyncio: mark a test function as running with an asyncio event loop.",
    )

    if config.getoption("pgvector") and not config.getoption("schema"):
        config.option.schema = True


def pytest_load_initial_conftests(
    early_config: pytest.Config, parser: pytest.Parser, args: list[str]
) -> None:
    """Ensure required plugins are available before parsing ini options."""

    _register_randomly_plugin(early_config.pluginmanager)


@pytest.fixture
def regression_factory():
    """Provide a seeded factory for synthesising regression datasets."""

    try:
        from tests.fixtures import RegressionDataFactory  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - thin local envs
        pytest.skip(f"faker not installed for regression factory: {exc}")
    except Exception as exc:  # pragma: no cover - guard against optional deps
        pytest.skip(f"regression fixtures unavailable: {exc}")
    return RegressionDataFactory()


@pytest.fixture
def application_container() -> Iterator[tuple["ApplicationContainer", "AdapterRegistry"]]:
    """Yield an isolated application container and backing registry."""

    with isolated_application_container() as resources:
        yield resources


@pytest.fixture
def application_container_factory():
    """Provide a factory returning isolated application containers."""

    def _factory(**overrides):
        return isolated_application_container(overrides=overrides or None)

    return _factory


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    """Execute ``async def`` tests without requiring pytest-asyncio."""

    if not inspect.iscoroutinefunction(pyfuncitem.obj):
        return None

    if pyfuncitem.get_closest_marker("asyncio") is None:
        return None

    testargs = {
        name: pyfuncitem.funcargs[name]
        for name in pyfuncitem._fixtureinfo.argnames  # type: ignore[attr-defined]
        if name in pyfuncitem.funcargs
    }
    asyncio.run(pyfuncitem.obj(**testargs))
    return True


os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("THEORIA_ENVIRONMENT", "development")


@pytest.fixture(scope="session", autouse=True)
def _configure_celery_for_tests() -> Generator[None, None, None]:
    """Execute Celery tasks inline to avoid external broker dependencies."""

    os.environ.setdefault("THEORIA_TESTING", "1")

    try:
        from theo.services.api.app.workers import tasks as worker_tasks
    except Exception:  # pragma: no cover - Celery optional in some test subsets
        yield
        return

    app = worker_tasks.celery
    previous_config = {
        "task_always_eager": app.conf.task_always_eager,
        "task_eager_propagates": app.conf.task_eager_propagates,
        "task_ignore_result": getattr(app.conf, "task_ignore_result", False),
        "task_store_eager_result": getattr(app.conf, "task_store_eager_result", False),
        "broker_url": app.conf.broker_url,
        "result_backend": app.conf.result_backend,
    }

    app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        task_ignore_result=True,
        task_store_eager_result=False,
        broker_url="memory://",
        result_backend=None,
    )

    try:
        yield
    finally:
        app.conf.update(**previous_config)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


_FIXTURE_MARKER_REQUIREMENTS: dict[str, set[str]] = {
    "pgvector": {
        "pgvector_container",
        "pgvector_database_url",
        "pgvector_engine",
        "pgvector_migrated_database_url",
    },
    "schema": {
        "integration_database_url",
        "integration_engine",
    },
}


_MARKER_OPTIONS: dict[str, str] = {
    "pgvector": "pgvector",
    "schema": "schema",
    "contract": "contract",
    "gpu": "gpu",
}


def _ensure_cli_opt_in(
    request: pytest.FixtureRequest, *, option: str, marker: str
) -> None:
    """Skip costly fixtures unless explicitly enabled via CLI flag."""

    if request.config.getoption(option):
        return

    cli_flag = option.replace("_", "-")
    pytest.skip(
        f"@pytest.mark.{marker} fixtures require the --{cli_flag} flag; "
        f"rerun with --{cli_flag} to enable this opt-in suite."
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Enforce marker usage and CLI opt-ins for costly test suites."""

    for item in items:
        fixture_names = set(item.fixturenames)

        for marker_name, fixtures in _FIXTURE_MARKER_REQUIREMENTS.items():
            if fixtures & fixture_names and item.get_closest_marker(marker_name) is None:
                fixtures_list = ", ".join(sorted(fixtures & fixture_names))
                cli_flag = _MARKER_OPTIONS[marker_name].replace("_", "-")
                raise pytest.UsageError(
                    " ".join(
                        [
                            f"{item.nodeid} uses fixture(s) {fixtures_list}",
                            f"but is missing @pytest.mark.{marker_name}.",
                            f"Mark the test and re-run with --{cli_flag}",
                            "to opt in to the heavy suite.",
                        ]
                    )
                )

        for marker_name, option_name in _MARKER_OPTIONS.items():
            if item.get_closest_marker(marker_name) and not config.getoption(option_name):
                cli_flag = option_name.replace("_", "-")
                item.add_marker(
                    pytest.mark.skip(
                        reason=f"requires --{cli_flag} opt-in to run @{marker_name} tests"
                    )
                )

POSTGRES_IMAGE = os.environ.get("PYTEST_PGVECTOR_IMAGE", "ankane/pgvector:0.5.2")


@pytest.fixture(scope="session")
def pgvector_container(
    request: pytest.FixtureRequest,
) -> Generator["PostgresContainer", None, None]:
    """Launch a pgvector-enabled Postgres container for integration tests."""

    _ensure_cli_opt_in(request, option="pgvector", marker="pgvector")

    try:
        from testcontainers.postgres import PostgresContainer
    except ModuleNotFoundError as exc:  # pragma: no cover - missing optional dep
        pytest.skip(f"testcontainers not installed: {exc}")

    container = PostgresContainer(image=POSTGRES_IMAGE)
    container.with_env("POSTGRES_DB", "theo")
    container.with_env("POSTGRES_USER", "postgres")
    container.with_env("POSTGRES_PASSWORD", "postgres")

    try:
        container.start()
    except Exception as exc:  # pragma: no cover - surfaced when Docker unavailable
        pytest.skip(f"Unable to start Postgres Testcontainer: {exc}")

    try:
        yield container
    finally:
        with contextlib.suppress(Exception):
            container.stop()


def _normalise_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@pytest.fixture(scope="session")
def pgvector_database_url(
    request: pytest.FixtureRequest, pgvector_container
) -> Generator[str, None, None]:
    """Yield a SQLAlchemy-friendly database URL for the running container."""

    _ensure_cli_opt_in(request, option="pgvector", marker="pgvector")

    raw_url = pgvector_container.get_connection_url()
    url = _normalise_database_url(raw_url)
    engine = create_engine(url, future=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        yield url
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def pgvector_engine(
    request: pytest.FixtureRequest, pgvector_database_url: str
) -> Generator[Engine, None, None]:
    """Provide a SQLAlchemy engine connected to the pgvector container."""

    _ensure_cli_opt_in(request, option="pgvector", marker="pgvector")

    engine = create_engine(pgvector_database_url, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def pgvector_migrated_database_url(
    request: pytest.FixtureRequest, pgvector_database_url: str
) -> Generator[str, None, None]:
    """Apply SQL migrations to the pgvector database and return the connection URL."""

    _ensure_cli_opt_in(request, option="schema", marker="schema")

    from theo.services.api.app.db.run_sql_migrations import run_sql_migrations

    engine = create_engine(pgvector_database_url, future=True)
    try:
        run_sql_migrations(engine)
        yield pgvector_database_url
    finally:
        engine.dispose()


def _sqlite_database_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Create a SQLite database URL with migrations applied."""
    from theo.services.api.app.db.run_sql_migrations import run_sql_migrations
    from theo.application.facades.database import Base

    database_dir = tmp_path_factory.mktemp("sqlite", numbered=True)
    path = database_dir / "test.db"
    url = f"sqlite:///{path}"

    # Create engine and apply migrations
    engine = create_engine(url, future=True)
    try:
        # First create all tables from models
        Base.metadata.create_all(bind=engine)
        # Then run migrations to ensure schema is up-to-date
        run_sql_migrations(engine)
        yield url
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def integration_database_url(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[str]:
    """Return a database URL backed by Postgres+pgvector when requested.

    Tests can opt in to a full pgvector-backed database via ``--use-pgvector``.
    Otherwise a throwaway SQLite database is created under the session's
    temporary directory. The fixture yields SQLAlchemy-compatible URLs so test
    suites can ``create_engine`` with minimal boilerplate.
    """

    if not request.config.getoption("schema"):
        pytest.skip(
            "@pytest.mark.schema fixtures require --schema (or --pgvector) opt-in"
        )

    if request.config.getoption("pgvector"):
        pgvector_url = request.getfixturevalue("pgvector_migrated_database_url")
        yield pgvector_url
        return

    yield from _sqlite_database_url(tmp_path_factory)


@pytest.fixture(scope="session")
def integration_engine(
    integration_database_url: str,
) -> Iterator[Engine]:
    """Provide a SQLAlchemy engine bound to the integration database."""

    engine = create_engine(integration_database_url, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _set_database_url_env(
    request: pytest.FixtureRequest, pytestconfig: pytest.Config
) -> Generator[None, None, None]:
    """Expose the integration database URL via ``DATABASE_URL``.

    Several subsystems rely on the ``DATABASE_URL`` environment variable during
    initialisation. Setting it once per test session avoids repeated fixture
    setup work while still restoring any pre-existing value afterwards.
    """

    if not pytestconfig.getoption("schema"):
        yield
        return

    integration_database_url = request.getfixturevalue("integration_database_url")
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = integration_database_url
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
