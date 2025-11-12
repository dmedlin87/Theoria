from __future__ import annotations

import os

# Force use of real FastAPI and Celery packages during testing
# This prevents import errors when shims don't expose all required submodules
os.environ["THEORIA_ALLOW_REAL_FASTAPI"] = "1"
os.environ["THEORIA_ALLOW_REAL_CELERY"] = "1"

import importlib
import importlib.util
import sys
import types
import warnings
from dataclasses import dataclass
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any, Callable

import pytest


pytest_plugins = [
    "tests.fixtures.research",
    "tests.fixtures.verses",
]


def _build_sqlalchemy_stub_modules() -> dict[str, types.ModuleType]:
    sqlalchemy_stub = types.ModuleType("sqlalchemy")

    class _Placeholder:
        def __init__(self, label: str) -> None:
            self._label = label

        def __call__(self, *_args: object, **_kwargs: object) -> "_Placeholder":
            return self

        def __getattr__(self, item: str) -> "_Placeholder":
            return _Placeholder(f"{self._label}.{item}")

        def with_variant(self, *_args: object, **_kwargs: object) -> "_Placeholder":
            return self

        def execution_options(self, *_args: object, **_kwargs: object) -> "_Placeholder":
            return self

        def where(self, *_args: object, **_kwargs: object) -> "_Placeholder":
            return self

        def join(self, *_args: object, **_kwargs: object) -> "_Placeholder":
            return self

        def order_by(self, *_args: object, **_kwargs: object) -> "_Placeholder":
            return self

        def select_from(self, *_args: object, **_kwargs: object) -> "_Placeholder":
            return self

    class _FuncProxy:
        def __getattr__(self, name: str) -> _Placeholder:
            return _Placeholder(f"func.{name}")

    def _raise(*_args: object, **_kwargs: object) -> _Placeholder:
        raise NotImplementedError("sqlalchemy placeholder accessed")

    sqlalchemy_stub.__theoria_sqlalchemy_stub__ = True
    sqlalchemy_stub.func = _FuncProxy()
    sqlalchemy_stub.select = _raise
    sqlalchemy_stub.create_engine = _raise
    sqlalchemy_stub.text = lambda statement: statement
    sqlalchemy_stub.cast = lambda *_args, **_kwargs: _Placeholder("cast")
    sqlalchemy_stub.or_ = lambda *_args, **_kwargs: _Placeholder("or")

    for name in [
        "JSON",
        "Boolean",
        "Date",
        "DateTime",
        "Enum",
        "Float",
        "ForeignKey",
        "Index",
        "Integer",
        "String",
        "Text",
        "UniqueConstraint",
    ]:
        setattr(sqlalchemy_stub, name, _Placeholder(name))

    exc_module = types.ModuleType("sqlalchemy.exc")

    class SQLAlchemyError(Exception):
        """Stub SQLAlchemyError used for import-time compatibility."""

    class ProgrammingError(SQLAlchemyError):
        pass

    exc_module.SQLAlchemyError = SQLAlchemyError
    exc_module.ProgrammingError = ProgrammingError

    orm_module = types.ModuleType("sqlalchemy.orm")

    class Session:  # pragma: no cover - placeholder
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise NotImplementedError("sqlalchemy.orm.Session placeholder accessed")

        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise NotImplementedError("sqlalchemy.orm.Session placeholder accessed")

    class DeclarativeBase:  # pragma: no cover - placeholder
        metadata: Any | None = None
        registry: Any | None = None

    orm_module.Session = Session
    orm_module.DeclarativeBase = DeclarativeBase
    orm_module.Mapped = Any  # type: ignore[assignment]
    orm_module.mapped_column = lambda *_args, **_kwargs: None
    orm_module.relationship = lambda *_args, **_kwargs: None
    orm_module.sessionmaker = lambda *_args, **_kwargs: None
    orm_module.joinedload = lambda *_args, **_kwargs: None

    engine_module = types.ModuleType("sqlalchemy.engine")

    class Engine:  # pragma: no cover - placeholder
        pass

    class Connection:  # pragma: no cover - placeholder
        pass

    engine_module.Engine = Engine
    engine_module.Connection = Connection

    dialects_module = types.ModuleType("sqlalchemy.dialects")
    postgresql_module = types.ModuleType("sqlalchemy.dialects.postgresql")
    postgresql_module.JSONB = _Placeholder("postgresql.JSONB")
    postgresql_module.ARRAY = _Placeholder("postgresql.ARRAY")
    sqlite_module = types.ModuleType("sqlalchemy.dialects.sqlite")
    sqlite_module.JSON = _Placeholder("sqlite.JSON")
    dialects_module.postgresql = postgresql_module
    dialects_module.sqlite = sqlite_module

    types_module = types.ModuleType("sqlalchemy.types")

    class TypeDecorator:  # pragma: no cover - placeholder
        cache_ok = True

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def __class_getitem__(cls, _item: object) -> "TypeDecorator":
            return cls

    types_module.TypeDecorator = TypeDecorator
    types_module.TEXT = _Placeholder("types.TEXT")

    sqltypes_module = types.ModuleType("sqlalchemy.sql.sqltypes")
    sqltypes_module.TypeEngine = TypeDecorator  # type: ignore[assignment]
    sqltypes_module.JSON = _Placeholder("sqltypes.JSON")
    sqltypes_module.INTEGER = lambda: _Placeholder("sqltypes.INTEGER")

    sql_module = types.ModuleType("sqlalchemy.sql")
    sql_module.sqltypes = sqltypes_module
    type_api_module = types.ModuleType("sqlalchemy.sql.type_api")
    type_api_module.TypeEngine = TypeDecorator
    sql_module.type_api = type_api_module

    pool_module = types.ModuleType("sqlalchemy.pool")

    class NullPool:  # pragma: no cover - placeholder
        pass

    pool_module.NullPool = NullPool

    return {
        "sqlalchemy": sqlalchemy_stub,
        "sqlalchemy.exc": exc_module,
        "sqlalchemy.orm": orm_module,
        "sqlalchemy.engine": engine_module,
        "sqlalchemy.dialects": dialects_module,
        "sqlalchemy.dialects.postgresql": postgresql_module,
        "sqlalchemy.dialects.sqlite": sqlite_module,
        "sqlalchemy.types": types_module,
        "sqlalchemy.sql": sql_module,
        "sqlalchemy.sql.sqltypes": sqltypes_module,
        "sqlalchemy.sql.type_api": type_api_module,
        "sqlalchemy.pool": pool_module,
    }


def _build_pythonbible_stub_module() -> types.ModuleType:
    module = types.ModuleType("pythonbible")

    class _BookEntry:
        def __init__(self, name: str) -> None:
            self.name = name

        def __repr__(self) -> str:  # pragma: no cover - debug helper
            return f"Book.{self.name}"

        def __hash__(self) -> int:
            return hash(self.name)

        def __eq__(self, other: object) -> bool:
            return isinstance(other, _BookEntry) and other.name == self.name

    class _BookMeta(type):
        def __iter__(cls) -> Iterable["_BookEntry"]:  # pragma: no cover
            return iter(cls._members)

    class Book(metaclass=_BookMeta):
        _members: list[_BookEntry] = []

    def _register(name: str) -> _BookEntry:
        entry = _BookEntry(name)
        setattr(Book, name, entry)
        Book._members.append(entry)
        return entry

    for book_name in [
        "GENESIS",
        "EXODUS",
        "LEVITICUS",
        "NUMBERS",
        "DEUTERONOMY",
        "JOSHUA",
        "JUDGES",
        "RUTH",
        "SAMUEL_1",
        "SAMUEL_2",
        "KINGS_1",
        "KINGS_2",
        "CHRONICLES_1",
        "CHRONICLES_2",
        "EZRA",
        "NEHEMIAH",
        "ESTHER",
        "JOB",
        "PSALMS",
        "PROVERBS",
        "ECCLESIASTES",
        "SONG_OF_SONGS",
        "ISAIAH",
        "JEREMIAH",
        "LAMENTATIONS",
        "EZEKIEL",
        "DANIEL",
        "HOSEA",
        "JOEL",
        "AMOS",
        "OBADIAH",
        "JONAH",
        "MICAH",
        "NAHUM",
        "HABAKKUK",
        "ZEPHANIAH",
        "HAGGAI",
        "ZECHARIAH",
        "MALACHI",
        "MATTHEW",
        "MARK",
        "LUKE",
        "JOHN",
        "ACTS",
        "ROMANS",
        "CORINTHIANS_1",
        "CORINTHIANS_2",
        "GALATIANS",
        "EPHESIANS",
        "PHILIPPIANS",
        "COLOSSIANS",
        "THESSALONIANS_1",
        "THESSALONIANS_2",
        "TIMOTHY_1",
        "TIMOTHY_2",
        "TITUS",
        "PHILEMON",
        "HEBREWS",
        "JAMES",
        "PETER_1",
        "PETER_2",
        "JOHN_1",
        "JOHN_2",
        "JOHN_3",
        "JUDE",
        "REVELATION",
        "TOBIT",
        "WISDOM_OF_SOLOMON",
        "ECCLESIASTICUS",
        "ESDRAS_1",
        "MACCABEES_1",
        "MACCABEES_2",
    ]:
        _register(book_name)

    @dataclass(frozen=True)
    class NormalizedReference:
        book: _BookEntry
        start_chapter: int
        start_verse: int
        end_chapter: int
        end_verse: int

    def is_valid_verse_id(verse_id: int) -> bool:  # pragma: no cover - stub
        return isinstance(verse_id, int) and verse_id >= 0

    module.Book = Book
    module.NormalizedReference = NormalizedReference
    module.is_valid_verse_id = is_valid_verse_id

    return module


def _build_cryptography_stub_modules() -> dict[str, types.ModuleType]:
    module = types.ModuleType("cryptography")
    fernet_module = types.ModuleType("cryptography.fernet")

    class Fernet:  # pragma: no cover - placeholder
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise NotImplementedError("cryptography.Fernet placeholder accessed")

    class InvalidToken(Exception):  # pragma: no cover - placeholder
        pass

    fernet_module.Fernet = Fernet
    fernet_module.InvalidToken = InvalidToken
    module.fernet = fernet_module

    return {
        "cryptography": module,
        "cryptography.fernet": fernet_module,
    }


def _build_httpx_stub_module() -> types.ModuleType:
    module = types.ModuleType("httpx")

    class HTTPStatusError(Exception):
        def __init__(self, message: str, request: object | None = None, response: object | None = None) -> None:
            super().__init__(message)
            self.request = request
            self.response = response

    class TimeoutException(Exception):
        pass

    class Timeout:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

    class Response:
        def __init__(self, status_code: int = 200, headers: dict[str, str] | None = None) -> None:
            self.status_code = status_code
            self.headers = headers or {}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise HTTPStatusError(f"HTTP {self.status_code}", response=self)

    class _BaseClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self._kwargs = _kwargs

        def request(self, *_args: object, **_kwargs: object) -> Response:
            return Response()

        def close(self) -> None:
            return None

    class Client(_BaseClient):
        pass

    class AsyncClient(_BaseClient):
        async def __aenter__(self) -> "AsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, *_args: object, **_kwargs: object) -> Response:
            return Response()

    module.Client = Client
    module.AsyncClient = AsyncClient
    module.Response = Response
    module.Timeout = Timeout
    module.TimeoutException = TimeoutException
    module.HTTPStatusError = HTTPStatusError

    return module


def _build_cachetools_stub_module() -> types.ModuleType:
    module = types.ModuleType("cachetools")

    class LRUCache(dict):  # pragma: no cover - placeholder
        def __init__(self, maxsize: int = 128, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            self.maxsize = maxsize

        def __setitem__(self, key: object, value: object) -> None:
            if key in self:
                super().__setitem__(key, value)
                return
            if len(self) >= self.maxsize:
                first_key = next(iter(self), None)
                if first_key is not None:
                    super().pop(first_key, None)
            super().__setitem__(key, value)

    module.LRUCache = LRUCache
    return module


def _build_settings_stub_module() -> types.ModuleType:
    module_name = "theo.application.facades.settings"
    settings_module = types.ModuleType(module_name)

    class Settings:  # pragma: no cover - placeholder
        def __init__(self) -> None:
            self.embedding_dim = 768

    def get_settings() -> Settings:  # pragma: no cover - placeholder
        return Settings()

    def _noop_cache_clear() -> None:  # pragma: no cover - placeholder
        return None

    get_settings.cache_clear = _noop_cache_clear  # type: ignore[attr-defined]

    settings_module.Settings = Settings
    settings_module.get_settings = get_settings
    settings_module.get_settings_secret = lambda: None
    settings_module.get_settings_cipher = lambda: None

    return settings_module


def _build_pydantic_stub_module() -> types.ModuleType:
    module = types.ModuleType("pydantic")

    class BaseModel:  # pragma: no cover - lightweight substitute
        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self, *_args: object, **_kwargs: object) -> dict[str, Any]:
            return dict(self.__dict__)

        def model_dump_json(self, *_args: object, **_kwargs: object) -> str:
            return repr(self.model_dump())

        @classmethod
        def model_validate(cls, data: dict[str, Any]) -> "BaseModel":
            return cls(**data)

    def Field(default: Any = None, **_kwargs: Any) -> Any:  # pragma: no cover - placeholder
        return default

    class ValidationError(Exception):  # pragma: no cover - placeholder
        pass

    def create_model(name: str, **fields: Any) -> type:
        return type(name, (BaseModel,), fields)

    module.BaseModel = BaseModel
    module.Field = Field
    module.ValidationError = ValidationError
    module.ConfigDict = dict
    module.create_model = create_model
    module.RootModel = BaseModel

    return module


def _install_optional_dependency_stubs() -> None:
    """Install stub modules for optional dependencies that are missing."""

    optional_modules: dict[str, Callable[[], dict[str, types.ModuleType]]] = {
        "sqlalchemy": _build_sqlalchemy_stub_modules,
        "pythonbible": lambda: {"pythonbible": _build_pythonbible_stub_module()},
        "httpx": lambda: {"httpx": _build_httpx_stub_module()},
        "cachetools": lambda: {"cachetools": _build_cachetools_stub_module()},
        "pydantic": lambda: {"pydantic": _build_pydantic_stub_module()},
    }

    for module_name, builder in optional_modules.items():
        if module_name in sys.modules:
            continue
        if importlib.util.find_spec(module_name) is not None:
            continue
        for name, module in builder().items():
            sys.modules.setdefault(name, module)


_install_optional_dependency_stubs()


@contextmanager
def _override_modules(
    modules: dict[str, types.ModuleType]
) -> Iterator[dict[str, types.ModuleType]]:
    """Temporarily replace entries in :mod:`sys.modules` with test doubles."""

    sentinel = object()
    originals: dict[str, object] = {}
    for name, module in modules.items():
        originals[name] = sys.modules.get(name, sentinel)
        sys.modules[name] = module
    try:
        yield modules
    finally:
        for name, original in originals.items():
            if original is sentinel:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original  # type: ignore[assignment]


@pytest.fixture
def stub_sqlalchemy() -> Iterator[types.ModuleType]:
    """Provide a lightweight SQLAlchemy shim for dependency-light tests."""

    with _override_modules(_build_sqlalchemy_stub_modules()) as installed:
        yield installed["sqlalchemy"]


@pytest.fixture
def stub_pythonbible() -> Iterator[types.ModuleType]:
    """Expose a minimal pythonbible replacement for tests that avoid the real package."""

    with _override_modules({"pythonbible": _build_pythonbible_stub_module()}) as installed:
        yield installed["pythonbible"]


@pytest.fixture
def stub_cryptography() -> Iterator[dict[str, types.ModuleType]]:
    """Install the cryptography.Fernet stub during the test body."""

    modules = _build_cryptography_stub_modules()
    with _override_modules(modules) as installed:
        yield installed


@pytest.fixture
def stub_httpx() -> Iterator[types.ModuleType]:
    """Yield a simple httpx module that mirrors the interface used in tests."""

    with _override_modules({"httpx": _build_httpx_stub_module()}) as installed:
        yield installed["httpx"]


@pytest.fixture
def stub_cachetools() -> Iterator[types.ModuleType]:
    """Expose a deterministic cachetools stub with :class:`LRUCache`."""

    with _override_modules({"cachetools": _build_cachetools_stub_module()}) as installed:
        yield installed["cachetools"]


@pytest.fixture
def stub_settings_facade() -> Iterator[types.ModuleType]:
    """Provide a pared-down settings facade for tests lacking secrets backends."""

    module_name = "theo.application.facades.settings"
    with _override_modules({module_name: _build_settings_stub_module()}) as installed:
        yield installed[module_name]

_HAS_PYTEST_TIMEOUT = importlib.util.find_spec("pytest_timeout") is not None


def pytest_addoption(parser):
    """Register custom options expected by the test configuration."""
    if not _HAS_PYTEST_TIMEOUT:
        parser.addoption(
            "--timeout",
            action="store",
            default=None,
            help=(
                "Ignored. Allows running the test suite without the pytest-timeout "
                "plugin installed."
            ),
        )
        warnings.filterwarnings(
            "ignore",
            message="pytest.PytestConfigWarning: Unknown config option: timeout",
        )
