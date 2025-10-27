"""Minimal SQLAlchemy stand-ins for CLI and unit tests."""

from __future__ import annotations

from importlib.machinery import ModuleSpec
from types import ModuleType, SimpleNamespace
from typing import Any

__all__ = ["build_sqlalchemy_stubs"]


class _FuncProxy:
    def __getattr__(self, name: str) -> Any:  # pragma: no cover - defensive
        raise NotImplementedError(f"sqlalchemy.func placeholder accessed for '{name}'")


def _raise(*_args: object, **_kwargs: object) -> None:  # pragma: no cover
    raise NotImplementedError("sqlalchemy placeholder accessed")


def _build_sqlalchemy_module() -> dict[str, ModuleType]:
    sqlalchemy_stub = ModuleType("sqlalchemy")
    sqlalchemy_stub.__path__ = []  # pragma: no cover - mark as package
    sqlalchemy_stub.__spec__ = ModuleSpec("sqlalchemy", loader=None, is_package=True)

    sqlalchemy_stub.func = _FuncProxy()
    sqlalchemy_stub.select = _raise
    sqlalchemy_stub.create_engine = _raise
    sqlalchemy_stub.text = lambda statement: statement

    exc_module = ModuleType("sqlalchemy.exc")

    class SQLAlchemyError(Exception):
        pass

    exc_module.SQLAlchemyError = SQLAlchemyError  # type: ignore[attr-defined]

    orm_module = ModuleType("sqlalchemy.orm")

    class Session:  # pragma: no cover - placeholder
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise NotImplementedError("sqlalchemy.orm.Session placeholder accessed")

    orm_module.Session = Session  # type: ignore[attr-defined]

    engine_module = ModuleType("sqlalchemy.engine")
    engine_module.Engine = SimpleNamespace  # type: ignore[attr-defined]

    sql_module = ModuleType("sqlalchemy.sql")
    sql_module.__path__ = []  # pragma: no cover - mark as package
    sql_module.__spec__ = ModuleSpec("sqlalchemy.sql", loader=None, is_package=True)

    elements_module = ModuleType("sqlalchemy.sql.elements")
    elements_module.__spec__ = ModuleSpec(
        "sqlalchemy.sql.elements", loader=None, is_package=True
    )

    class ClauseElement:  # pragma: no cover - placeholder
        pass

    elements_module.ClauseElement = ClauseElement  # type: ignore[attr-defined]
    sql_module.elements = elements_module  # type: ignore[attr-defined]

    return {
        "sqlalchemy": sqlalchemy_stub,
        "sqlalchemy.exc": exc_module,
        "sqlalchemy.orm": orm_module,
        "sqlalchemy.engine": engine_module,
        "sqlalchemy.sql": sql_module,
        "sqlalchemy.sql.elements": elements_module,
    }


def build_sqlalchemy_stubs() -> dict[str, ModuleType]:
    """Return a mapping of module names for the SQLAlchemy shim."""

    return _build_sqlalchemy_module()
