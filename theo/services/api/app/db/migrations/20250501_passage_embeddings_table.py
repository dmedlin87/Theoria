from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, MetaData, String, Table, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from theo.application.facades.settings import get_settings
from theo.adapters.persistence.types import VectorType


def upgrade(*, session: Session, engine: Engine) -> None:  # pragma: no cover - executed via migration runner
    metadata = MetaData()
    settings = get_settings()

    passage_embeddings = Table(
        "passage_embeddings",
        metadata,
        Column(
            "passage_id",
            String,
            ForeignKey("passages.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        Column("embedding", VectorType(settings.embedding_dim), nullable=False),
        Column(
            "created_at",
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
        Column(
            "updated_at",
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
        ),
    )

    metadata.create_all(bind=engine)

    # Backfill any existing passage embeddings into the new table before dropping the column.
    rows = session.execute(
        text("SELECT id, embedding FROM passages WHERE embedding IS NOT NULL")
    ).all()
    if rows:
        session.execute(
            passage_embeddings.insert(),
            [
                {"passage_id": row.id, "embedding": row.embedding}
                for row in rows
                if getattr(row, "embedding", None) is not None
            ],
        )
        session.flush()

    session.execute(text("ALTER TABLE passages DROP COLUMN embedding"))
    session.flush()


__all__ = ["upgrade"]
