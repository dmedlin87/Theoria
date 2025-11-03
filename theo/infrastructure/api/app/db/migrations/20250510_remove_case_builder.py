"""Drop legacy Case Builder tables and supporting schema."""

from __future__ import annotations

from sqlalchemy import MetaData, Table, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def _drop_table_if_exists(engine: Engine, name: str) -> None:
    inspector = inspect(engine)
    if not inspector.has_table(name):
        return
    metadata = MetaData()
    table = Table(name, metadata, autoload_with=engine)
    table.drop(bind=engine, checkfirst=True)


def upgrade(*, session: Session, engine: Engine) -> None:  # pragma: no cover - executed via migration runner
    inspector = inspect(engine)

    # Drop dependent tables first to satisfy foreign key constraints.
    for table_name in (
        "case_user_actions",
        "case_insights",
        "case_edges",
        "case_objects",
        "case_sources",
    ):
        _drop_table_if_exists(engine, table_name)

    # Remove the Case Builder foreign key from document annotations if present.
    if inspector.has_table("document_annotations"):
        column_names = {column["name"] for column in inspector.get_columns("document_annotations")}
        if "case_object_id" in column_names:
            session.execute(text("ALTER TABLE document_annotations DROP COLUMN case_object_id"))

    # Drop the enum types defined for Case Builder when running on PostgreSQL.
    if engine.dialect.name == "postgresql":
        for enum_name in (
            "case_user_action_type",
            "case_insight_type",
            "case_edge_kind",
            "case_object_type",
        ):
            session.execute(text(f"DROP TYPE IF EXISTS {enum_name}"))

    session.flush()
