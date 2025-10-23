"""Create tables for discoveries and corpus snapshots."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
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


def _boolean_default(engine: Engine) -> text:
    if engine.dialect.name == "postgresql":
        return text("false")
    return text("0")


def upgrade(*, session: Session, engine: Engine) -> None:  # pragma: no cover - executed via migration runner
    metadata = MetaData()
    json_type = _json_type(engine)
    bool_default = _boolean_default(engine)

    discoveries = Table(
        "discoveries",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", String, nullable=False),
        Column("discovery_type", String, nullable=False),
        Column("title", String, nullable=False),
        Column("description", Text, nullable=True),
        Column("confidence", Float, nullable=False, server_default=text("0")),
        Column("relevance_score", Float, nullable=False, server_default=text("0")),
        Column("viewed", Boolean, nullable=False, server_default=bool_default),
        Column("user_reaction", String, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
        Column("meta", json_type, nullable=True),
    )
    Index("ix_discoveries_user_id", discoveries.c.user_id)
    Index("ix_discoveries_created_at", discoveries.c.created_at)
    Index("ix_discoveries_discovery_type", discoveries.c.discovery_type)
    Index("ix_discoveries_viewed", discoveries.c.viewed)

    corpus_snapshots = Table(
        "corpus_snapshots",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", String, nullable=False),
        Column("snapshot_date", DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
        Column("document_count", Integer, nullable=False, server_default=text("0")),
        Column("verse_coverage", json_type, nullable=True),
        Column("dominant_themes", json_type, nullable=True),
        Column("meta", json_type, nullable=True),
    )
    Index("ix_corpus_snapshots_user_id", corpus_snapshots.c.user_id)

    metadata.create_all(bind=engine)
    session.flush()
