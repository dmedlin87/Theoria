from __future__ import annotations

import asyncio
import contextlib
from contextvars import ContextVar
import gc
import importlib
import inspect
import os
import sys
import types
import warnings
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:  # pragma: no cover - imported only for type checking
    from theo.adapters import AdapterRegistry
    from theo.application import ApplicationContainer
    from tests.fixtures import RegressionDataFactory
    from testcontainers.postgres import PostgresContainer

import pytest


def _ensure_celery_pytest_plugin() -> None:
    """Load the bundled Celery pytest plugin when the real dependency is absent."""

    repo_root = Path(__file__).resolve().parents[1]
    celery_module = sys.modules.get("celery")
    if celery_module is not None and not hasattr(celery_module, "__path__"):
        celery_module.__path__ = [str(repo_root / "celery")]  # type: ignore[attr-defined]

    try:
        importlib.import_module("celery.contrib.pytest")
        return
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", "celery.contrib.pytest")
        if missing not in {"celery", "celery.contrib", "celery.contrib.pytest"}:
            raise

    plugin_path = repo_root / "celery" / "contrib" / "pytest.py"
    if not plugin_path.exists():
        return

    celery_pkg = sys.modules.get("celery")
    if celery_pkg is None:
        celery_pkg = types.ModuleType("celery")
        celery_pkg.__path__ = [str(repo_root / "celery")]  # type: ignore[attr-defined]
        sys.modules["celery"] = celery_pkg
    elif not hasattr(celery_pkg, "__path__"):
        celery_pkg.__path__ = [str(repo_root / "celery")]  # type: ignore[attr-defined]

    contrib_name = "celery.contrib"
    contrib_mod = sys.modules.get(contrib_name)
    if contrib_mod is None:
        contrib_mod = types.ModuleType(contrib_name)
        contrib_mod.__path__ = [str(repo_root / "celery" / "contrib")]  # type: ignore[attr-defined]
        setattr(celery_pkg, "contrib", contrib_mod)  # type: ignore[attr-defined]
        sys.modules[contrib_name] = contrib_mod

    spec = importlib.util.spec_from_file_location("celery.contrib.pytest", str(plugin_path))
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules["celery.contrib.pytest"] = module
        setattr(contrib_mod, "pytest", module)  # type: ignore[attr-defined]
        spec.loader.exec_module(module)


_ensure_celery_pytest_plugin()

try:  # pragma: no cover - optional dependency
    import pydantic  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - lightweight CI environments
    pydantic = types.ModuleType("pydantic")  # type: ignore[assignment]
    sys.modules["pydantic"] = pydantic

if not hasattr(pydantic, "BaseModel"):
    class _BaseModel:
        def __init__(self, **_kwargs: object) -> None:
            pass

    pydantic.BaseModel = _BaseModel  # type: ignore[attr-defined]


def _identity_decorator(*_args: object, **_kwargs: object):  # pragma: no cover - helper
    def _decorator(func: Any) -> Any:
        return func

    return _decorator


if not hasattr(pydantic, "Field"):
    def _field(*_args: object, **_kwargs: object) -> None:
        return None

    pydantic.Field = _field  # type: ignore[attr-defined]

if not hasattr(pydantic, "field_validator"):
    pydantic.field_validator = _identity_decorator  # type: ignore[attr-defined]

if not hasattr(pydantic, "model_validator"):
    pydantic.model_validator = _identity_decorator  # type: ignore[attr-defined]

if not hasattr(pydantic, "AliasChoices"):
    class _AliasChoices:
        def __init__(self, *_choices: object) -> None:
            self.choices = _choices

    pydantic.AliasChoices = _AliasChoices  # type: ignore[attr-defined]

if not hasattr(pydantic, "model_serializer"):
    pydantic.model_serializer = _identity_decorator  # type: ignore[attr-defined]

if "pydantic_settings" not in sys.modules:  # pragma: no cover - lightweight CI environments
    spec = importlib.util.find_spec("pydantic_settings")
    if spec is None:
        pydantic_settings = types.ModuleType("pydantic_settings")

        class _BaseSettings:
            model_config: dict[str, object] = {}

            def __init__(self, **_kwargs: object) -> None:
                pass

        pydantic_settings.BaseSettings = _BaseSettings  # type: ignore[attr-defined]
        pydantic_settings.SettingsConfigDict = dict  # type: ignore[attr-defined]

        sys.modules["pydantic_settings"] = pydantic_settings

try:  # pragma: no cover - optional dependency for integration fixtures
    import importlib
    import sqlalchemy
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Connection, Engine
    from sqlalchemy.orm import Session, sessionmaker
    try:
        event = sqlalchemy.event
    except AttributeError:  # pragma: no cover - minimal SQLAlchemy stubs
        event = importlib.import_module("sqlalchemy.event")
except (ModuleNotFoundError, ImportError):  # pragma: no cover - allows running lightweight suites
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]
    Connection = object  # type: ignore[assignment]
    Engine = object  # type: ignore[assignment]
    Session = object  # type: ignore[assignment]
    sessionmaker = None  # type: ignore[assignment]
    
    class _EventStub:  # pragma: no cover - lightweight environments skip DB tests
        @staticmethod
        def listens_for(*_args: object, **_kwargs: object):
            def _decorator(func):
                return func

            return _decorator

        @staticmethod
        def remove(*_args: object, **_kwargs: object) -> None:
            return None

    event = _EventStub()  # type: ignore[assignment]

try:  # pragma: no cover - factory depends on optional domain extras
    from tests.factories.application import isolated_application_container
    from tests.fixtures.pgvector import (
        PGVectorDatabase,
        PGVectorClone,
        provision_pgvector_database,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - light environments
    isolated_application_container = None  # type: ignore[assignment]
    _APPLICATION_FACTORY_IMPORT_ERROR = exc
else:
    _APPLICATION_FACTORY_IMPORT_ERROR: ModuleNotFoundError | None = None


_SQLALCHEMY_AVAILABLE = create_engine is not None

if not _SQLALCHEMY_AVAILABLE:

    def _sqlalchemy_missing(*_args: object, **_kwargs: object):  # type: ignore[misc]
        pytest.skip("sqlalchemy not installed")

    create_engine = _sqlalchemy_missing  # type: ignore[assignment]
    text = _sqlalchemy_missing  # type: ignore[assignment]


def _require_application_factory() -> None:
    if isolated_application_container is None:
        reason = _APPLICATION_FACTORY_IMPORT_ERROR or ModuleNotFoundError("pythonbible")
        pytest.skip(f"application factory unavailable: {reason}")

if os.environ.get("THEORIA_SKIP_HEAVY_FIXTURES", "0") not in {"1", "true", "TRUE"}:
    try:
        import pydantic  # type: ignore  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover - exercised in lightweight envs
        warnings.warn(
            "pydantic not installed; skipping heavy pytest fixtures that depend on it.",
            RuntimeWarning,
        )
        pytest_plugins = []
    else:
        pytest_plugins = ["tests.fixtures.mocks"]
else:  # pragma: no cover - exercised in lightweight CI and profiling flows
    pytest_plugins: list[str] = []

try:  # pragma: no cover - optional dependency in local test harness
    import pytest_cov  # type: ignore  # noqa: F401

    _HAS_PYTEST_COV = True
except ModuleNotFoundError:  # pragma: no cover - executed when plugin is missing
    _HAS_PYTEST_COV = False

try:  # pragma: no cover - psutil optional for lightweight environments
    import psutil
except ModuleNotFoundError:  # pragma: no cover - allows running without psutil
    psutil = None  # type: ignore[assignment]
    _PSUTIL_PROCESS = None
else:  # pragma: no cover - process lookup can fail in sandboxes
    try:
        _PSUTIL_PROCESS = psutil.Process()
    except Exception:
        _PSUTIL_PROCESS = None

_ENABLE_MEMCHECK = os.getenv("THEORIA_MEMCHECK", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_SCHEMA_CONNECTION: ContextVar[Connection | None] = ContextVar("_SCHEMA_CONNECTION")


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


def _register_xdist_plugin(pluginmanager: pytest.PluginManager) -> bool:
    """Ensure pytest-xdist is eagerly registered when the dependency exists."""

    if pluginmanager.hasplugin("xdist"):
        return True

    try:
        plugin_module = importlib.import_module("xdist.plugin")
    except ModuleNotFoundError:
        return False

    pluginmanager.register(plugin_module, "xdist")
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

    _register_xdist_plugin(config.pluginmanager)

    config.addinivalue_line(
        "markers",
        "asyncio: mark a test function as running with an asyncio event loop.",
    )
    config.addinivalue_line(
        "markers",
        "allow_sleep: opt out of the session-wide sleep patches for a test.",
    )
    config.addinivalue_line(
        "markers",
        "memcheck: enable the manage_memory fixture for targeted leak hunts.",
    )

    if config.getoption("pgvector") and not config.getoption("schema"):
        config.option.schema = True


def pytest_load_initial_conftests(
    early_config: pytest.Config, parser: pytest.Parser, args: list[str]
) -> None:
    """Ensure required plugins are available before parsing ini options."""

    _register_randomly_plugin(early_config.pluginmanager)
    _register_xdist_plugin(early_config.pluginmanager)


@pytest.fixture
def regression_factory():
    """Provide a seeded factory for synthesising regression datasets."""

    try:
        from tests.fixtures import (  # type: ignore
            REGRESSION_FIXTURES_AVAILABLE,
            REGRESSION_IMPORT_ERROR,
            RegressionDataFactory,
        )
    except ModuleNotFoundError as exc:  # pragma: no cover - thin local envs
        pytest.skip(f"faker not installed for regression factory: {exc}")
    except Exception as exc:  # pragma: no cover - guard against optional deps
        pytest.skip(f"regression fixtures unavailable: {exc}")
    if not REGRESSION_FIXTURES_AVAILABLE:
        reason = REGRESSION_IMPORT_ERROR or ModuleNotFoundError("unknown dependency")
        pytest.skip(f"regression fixtures unavailable: {reason}")
    return RegressionDataFactory()


@pytest.fixture
def application_container() -> Iterator[tuple["ApplicationContainer", "AdapterRegistry"]]:
    """Yield an isolated application container and backing registry."""

    _require_application_factory()
    with isolated_application_container() as resources:
        yield resources


@pytest.fixture(scope="session")
def optimized_application_container() -> Generator[
    tuple["ApplicationContainer", "AdapterRegistry"], None, None
]:
    """Create the application container once per session for heavy suites."""

    _require_application_factory()
    with isolated_application_container() as resources:
        yield resources


@pytest.fixture
def application_container_factory():
    """Provide a factory returning isolated application containers."""

    _require_application_factory()

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
        from theo.infrastructure.api.app.workers import tasks as worker_tasks
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
        "ingest_engine",
        "pgvector_db",
        "pgvector_container",
        "pgvector_database_url",
        "pgvector_engine",
        "pgvector_migrated_database_url",
        "pipeline_engine",
        "pipeline_session_factory",
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


def _resolve_xdist_group(item: pytest.Item) -> str | None:
    """Return the logical xdist group for a collected test item."""

    keywords = item.keywords
    if "db" in keywords or "schema" in keywords:
        return "database"

    if "network" in keywords:
        return "network"

    if "gpu" in keywords:
        return "ml"

    item_path = Path(str(getattr(item, "path", getattr(item, "fspath", ""))))
    lower_parts = {part.lower() for part in item_path.parts}
    if "ml" in lower_parts or "gpu" in lower_parts:
        return "ml"

    return None


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

    has_xdist = config.pluginmanager.hasplugin("xdist")

    for item in items:
        if not _ENABLE_MEMCHECK and item.get_closest_marker("memcheck"):
            item.add_marker(pytest.mark.usefixtures("manage_memory"))

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

        if item.get_closest_marker("schema"):
            item.add_marker(pytest.mark.usefixtures("schema_isolation"))

        if has_xdist:
            group_name = _resolve_xdist_group(item)
            if group_name is None:
                continue

            existing_groups = {
                marker.kwargs.get("name")
                for marker in item.iter_markers(name="xdist_group")
            }
            if group_name not in existing_groups:
                item.add_marker(pytest.mark.xdist_group(name=group_name))


POSTGRES_IMAGE = os.environ.get("PYTEST_PGVECTOR_IMAGE", "pgvector/pgvector:pg15")


@pytest.fixture(scope="session")
def pgvector_db(request: pytest.FixtureRequest) -> Iterator[PGVectorDatabase]:
    """Provision a seeded Postgres+pgvector database for heavy integration suites.

    The fixture starts a single Testcontainer for the duration of the test
    session, applies the project's SQL migrations, and seeds the bundled
    reference datasets.  Individual tests can call ``clone_database`` on the
    returned object to create isolated databases that inherit the prepared
    schema and extensions without incurring the full migration cost again.
    """

    _ensure_cli_opt_in(request, option="pgvector", marker="pgvector")

    try:
        context = provision_pgvector_database(image=POSTGRES_IMAGE)
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        pytest.skip(f"testcontainers not installed: {exc}")
    try:
        with context as database:
            yield database
    except ModuleNotFoundError as exc:  # pragma: no cover - container provisioning
        pytest.skip(f"testcontainers not installed: {exc}")
    except Exception as exc:  # pragma: no cover - surfaced when Docker unavailable
        pytest.skip(f"Unable to start Postgres Testcontainer: {exc}")


@pytest.fixture(scope="session")
def pgvector_container(pgvector_db: PGVectorDatabase) -> PostgresContainer:
    """Return the underlying Testcontainer for backwards-compatible fixtures."""

    return pgvector_db.container


@pytest.fixture(scope="session")
def pgvector_database_url(pgvector_db: PGVectorDatabase) -> str:
    """Expose the SQLAlchemy URL for the seeded pgvector template database."""

    return pgvector_db.url


@pytest.fixture(scope="session")
def pgvector_engine(pgvector_db: PGVectorDatabase) -> Iterator[Engine]:
    """Yield an engine connected to the seeded pgvector template database."""

    engine = pgvector_db.create_engine()
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def pgvector_migrated_database_url(pgvector_db: PGVectorDatabase) -> str:
    """Return the URL of the migrated pgvector database (for legacy callers)."""

    return pgvector_db.url


def _initialise_shared_database(db_path: Path) -> str:
    from theo.application.facades.database import Base
    from theo.infrastructure.api.app.db.run_sql_migrations import run_sql_migrations

    url = f"sqlite:///{db_path}"
    engine = create_engine(url, future=True)
    try:
        Base.metadata.create_all(bind=engine)
        run_sql_migrations(engine)
    finally:
        engine.dispose()

    return url


def _load_model_from_registry(model_name: str) -> Any:
    """Attempt to import an expensive ML model using common naming conventions."""

    candidate_modules = [
        f"theo.ml.models.{model_name}",
        f"theo.infrastructure.ml.{model_name}",
        f"theo.infrastructure.ml.models.{model_name}",
        f"theo.infrastructure.api.app.ml.{model_name}",
        f"theo.infrastructure.api.app.ml.models.{model_name}",
    ]

    for module_path in candidate_modules:
        with contextlib.suppress(ModuleNotFoundError, AttributeError):
            module = importlib.import_module(module_path)
            loader = getattr(module, "load_model")
            if callable(loader):
                return loader()

    raise LookupError(f"Unable to locate loader for ML model '{model_name}'")


def _sqlite_database_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Create a SQLite database URL with migrations applied."""
    from theo.infrastructure.api.app.db.run_sql_migrations import run_sql_migrations
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
        migrations_module = importlib.import_module(
            "theo.infrastructure.api.app.db.run_sql_migrations"
        )
        original_index_helper = getattr(
            migrations_module, "_ensure_performance_indexes", None
        )
        try:
            if original_index_helper is not None:
                migrations_module._ensure_performance_indexes = (  # type: ignore[attr-defined]
                    lambda _engine: []
                )
            run_sql_migrations(engine)
        finally:
            if original_index_helper is not None:
                migrations_module._ensure_performance_indexes = (  # type: ignore[attr-defined]
                    original_index_helper
                )
        yield url
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def shared_test_database(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Create a session-scoped SQLite database that can be reused across tests."""

    database_dir = tmp_path_factory.mktemp("shared_db", numbered=False)
    db_path = database_dir / "test.db"
    return _initialise_shared_database(db_path)


@pytest.fixture(scope="session")
def ml_models() -> Callable[[str], Any]:
    """Load expensive ML models lazily and cache them for reuse."""

    cache: dict[str, Any] = {}

    def _load(model_name: str, *, loader: Callable[[], Any] | None = None) -> Any:
        if model_name not in cache:
            if loader is not None:
                cache[model_name] = loader()
            else:
                cache[model_name] = _load_model_from_registry(model_name)
        return cache[model_name]

    return _load


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


@pytest.fixture(scope="function")
def db_transaction(integration_engine: Engine) -> Generator[Any, None, None]:
    """Wrap tests in a transaction that is rolled back afterwards."""

    connection = integration_engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def integration_session(request: pytest.FixtureRequest) -> Generator[Session, None, None]:
    """Return a SQLAlchemy ``Session`` bound to an isolated transaction."""

    if sessionmaker is None:  # pragma: no cover - lightweight envs without SQLAlchemy
        pytest.skip("sqlalchemy not installed")

    connection = _SCHEMA_CONNECTION.get(None)
    if connection is None:
        db_transaction = request.getfixturevalue("db_transaction")
        connection = cast("Connection", db_transaction)
    else:
        connection = cast("Connection", connection)

    SessionFactory = sessionmaker(bind=connection, future=True)  # type: ignore[arg-type]
    session = SessionFactory()
    nested = session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, transaction) -> None:  # type: ignore[no-redef]
        if transaction.nested and not transaction._parent.nested:  # pragma: no branch - mirrored from SQLAlchemy recipe
            sess.begin_nested()

    try:
        yield session
    finally:
        try:
            if nested.is_active:
                nested.rollback()
        except Exception:  # pragma: no cover - defensive cleanup
            pass
        event.remove(session, "after_transaction_end", _restart_savepoint)
        session.close()


@pytest.fixture(scope="function")
def schema_isolation(db_transaction: Any) -> Iterator[Any]:
    """Ensure ``@pytest.mark.schema`` tests automatically roll back state."""

    connection = cast("Connection", db_transaction)
    token = _SCHEMA_CONNECTION.set(connection)
    try:
        yield connection
    finally:
        _SCHEMA_CONNECTION.reset(token)


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


@pytest.fixture(autouse=_ENABLE_MEMCHECK)
def manage_memory() -> Generator[None, None, None]:
    """Collect garbage eagerly and warn about potential leaks."""

    process = _PSUTIL_PROCESS
    before = process.memory_info().rss if process is not None else 0

    yield

    gc.collect()

    if process is None or before == 0:
        return

    after = process.memory_info().rss
    if after > before * 1.5:
        warnings.warn(
            "Potential memory leak detected in test execution",
            ResourceWarning,
            stacklevel=2,
        )


@pytest.fixture(scope="session", autouse=True)
def mock_sleep_session() -> dict[str, Any]:
    """Patch sleep functions once per session to minimise fixture churn."""

    async_sleep_mock = AsyncMock()
    time_patcher = patch("time.sleep", return_value=None)
    asyncio_patcher = patch("asyncio.sleep", new=async_sleep_mock)

    time_patcher.start()
    asyncio_patcher.start()
    try:
        yield {
            "time": time_patcher,
            "asyncio": asyncio_patcher,
            "async_mock": async_sleep_mock,
        }
    finally:
        asyncio_patcher.stop()
        time_patcher.stop()


@pytest.fixture(autouse=True)
def mock_sleep(request, mock_sleep_session: dict[str, Any]) -> Iterator[None]:
    patchers = mock_sleep_session
    async_mock: AsyncMock = patchers["async_mock"]

    if "allow_sleep" in request.keywords:
        time_patcher = patchers["time"]
        asyncio_patcher = patchers["asyncio"]
        asyncio_patcher.stop()
        time_patcher.stop()
        try:
            yield
        finally:
            time_patcher.start()
            asyncio_patcher.start()
            async_mock.reset_mock()
        return

    try:
        yield
    finally:
        async_mock.reset_mock()


class TestResourcePool:
    """Pool expensive resources for reuse across the test session."""

    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}

    def get_db_engine(self, url: str) -> Engine:
        engine = self._engines.get(url)
        if engine is None:
            engine = create_engine(url, future=True)
            self._engines[url] = engine
        return engine

    def cleanup(self) -> None:
        for engine in self._engines.values():
            engine.dispose()
        self._engines.clear()


@pytest.fixture(scope="session")
def resource_pool() -> Generator[TestResourcePool, None, None]:
    """Expose a shared resource pool for integration-heavy tests."""

    pool = TestResourcePool()
    try:
        yield pool
    finally:
        pool.cleanup()
