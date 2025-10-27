from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.sql.elements import ClauseElement

from theo.infrastructure.api.app.ingest.embeddings import lexical_representation


def _session_with_dialect(name: str) -> SimpleNamespace:
    dialect = SimpleNamespace(name=name)
    bind = SimpleNamespace(dialect=dialect)
    return SimpleNamespace(bind=bind)


def test_lexical_representation_sqlite_normalises_punctuation() -> None:
    session = _session_with_dialect("sqlite")
    text = "Alpha, beta!  \nNew-line; 123 -- co-operate's?"

    representation = lexical_representation(session, text)

    assert representation == "alpha beta new line 123 co operate s"


def test_lexical_representation_sqlite_preserves_unicode_letters() -> None:
    session = _session_with_dialect("sqlite")
    text = "Café ἀγάπη -- Привет!"

    representation = lexical_representation(session, text)

    assert representation == "café ἀγάπη привет"


def test_lexical_representation_postgres_returns_clause_element() -> None:
    session = _session_with_dialect("postgresql")

    representation = lexical_representation(session, "Hello world")

    assert isinstance(representation, ClauseElement)
