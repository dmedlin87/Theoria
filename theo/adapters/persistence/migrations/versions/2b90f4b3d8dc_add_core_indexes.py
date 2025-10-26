"""Add indexes for passages and documents performance."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "2b90f4b3d8dc"
down_revision = None
branch_labels = None
depends_on = None

_POSTGRES_CREATE = (
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_passages_embedding_null "
    "ON passages (id) WHERE embedding IS NULL",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_updated_at "
    "ON documents (updated_at)",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_passages_document_id "
    "ON passages (document_id)",
)

_GENERIC_CREATE = (
    "CREATE INDEX IF NOT EXISTS idx_passages_embedding_null "
    "ON passages (id) WHERE embedding IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents (updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_passages_document_id ON passages (document_id)",
)

_POSTGRES_DROP = (
    "DROP INDEX CONCURRENTLY IF EXISTS idx_passages_embedding_null",
    "DROP INDEX CONCURRENTLY IF EXISTS idx_documents_updated_at",
    "DROP INDEX CONCURRENTLY IF EXISTS idx_passages_document_id",
)

_GENERIC_DROP = (
    "DROP INDEX IF EXISTS idx_passages_embedding_null",
    "DROP INDEX IF EXISTS idx_documents_updated_at",
    "DROP INDEX IF EXISTS idx_passages_document_id",
)


def _dialect_name() -> str | None:
    context = op.get_context()
    dialect = getattr(context, "dialect", None)
    return getattr(dialect, "name", None)


def upgrade() -> None:
    dialect_name = _dialect_name()
    statements = _POSTGRES_CREATE if dialect_name == "postgresql" else _GENERIC_CREATE

    for statement in statements:
        if dialect_name == "postgresql":
            with op.get_context().autocommit_block():
                op.execute(sa.text(statement))
        else:
            op.execute(sa.text(statement))


def downgrade() -> None:
    dialect_name = _dialect_name()
    statements = _POSTGRES_DROP if dialect_name == "postgresql" else _GENERIC_DROP

    for statement in statements:
        if dialect_name == "postgresql":
            with op.get_context().autocommit_block():
                op.execute(sa.text(statement))
        else:
            op.execute(sa.text(statement))
