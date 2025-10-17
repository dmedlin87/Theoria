from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def _json_type(engine: Engine) -> JSON:
    if engine.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=Text())
    return JSON


def _json_default(engine: Engine) -> text:
    if engine.dialect.name == "postgresql":
        return text("'{}'::jsonb")
    return text("'{}'")


def upgrade(*, session: Session, engine: Engine) -> None:  # pragma: no cover - executed via migration runner
    metadata = MetaData()
    json_type = _json_type(engine)
    json_default = _json_default(engine)

    audit_logs = Table(
        "audit_logs",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("workflow", String, nullable=False),
        Column("status", String, nullable=False, server_default=text("'generated'")),
        Column("prompt_hash", String, nullable=False),
        Column("model_preset", String, nullable=True),
        Column("inputs", json_type, nullable=False, server_default=json_default),
        Column("outputs", json_type, nullable=True),
        Column("citations", json_type, nullable=True),
        Column(
            "created_at",
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    Index("ix_audit_logs_prompt_hash", audit_logs.c.prompt_hash)
    Index(
        "ix_audit_logs_workflow_created_at",
        audit_logs.c.workflow,
        audit_logs.c.created_at,
    )

    metadata.create_all(bind=engine)
    session.flush()
