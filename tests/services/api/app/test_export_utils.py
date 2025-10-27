from __future__ import annotations

from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
import types

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from theo.adapters.persistence import Base
from theo.adapters.persistence.models import Document, Passage

_MODULE_PATH = Path(__file__).resolve().parents[4] / "theo" / "services" / "api" / "app" / "routes" / "export" / "utils.py"
_EXPORT_PACKAGE = "theo.infrastructure.api.app.routes.export"
if _EXPORT_PACKAGE not in sys.modules:
    export_module = types.ModuleType(_EXPORT_PACKAGE)
    export_module.__path__ = [str(_MODULE_PATH.parent)]  # type: ignore[attr-defined]
    sys.modules[_EXPORT_PACKAGE] = export_module

_SPEC = importlib.util.spec_from_file_location(
    f"{_EXPORT_PACKAGE}.utils", _MODULE_PATH
)
assert _SPEC and _SPEC.loader is not None
_EXPORT_UTILS = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _EXPORT_UTILS
_SPEC.loader.exec_module(_EXPORT_UTILS)
fetch_documents_by_ids = _EXPORT_UTILS.fetch_documents_by_ids


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@contextmanager
def _record_selects(session: Session):
    statements: list[str] = []
    engine = session.get_bind()

    def _before_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _before_execute)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _before_execute)


def test_fetch_documents_by_ids_eager_loads_passages(session: Session) -> None:
    doc_one = Document(id="doc-1", title="First Document")
    doc_one.passages.extend(
        [
            Passage(id="passage-1", text="First", document_id="doc-1"),
        ]
    )
    doc_two = Document(id="doc-2", title="Second Document")
    doc_two.passages.extend(
        [
            Passage(id="passage-2", text="Second", document_id="doc-2"),
        ]
    )
    session.add_all([doc_one, doc_two])
    session.commit()

    with _record_selects(session) as statements:
        documents = fetch_documents_by_ids(session, ["doc-1", "doc-2"])
        assert [doc.id for doc in documents] == ["doc-1", "doc-2"]
        lengths = [len(doc.passages) for doc in documents]
        assert lengths == [1, 1]

    select_statements = [stmt for stmt in statements if stmt.lstrip().upper().startswith("SELECT")]
    assert len(select_statements) <= 2
