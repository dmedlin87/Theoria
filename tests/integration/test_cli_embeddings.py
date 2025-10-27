from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy.orm import Session

from theo.application.facades.settings import get_settings
from theo.cli import rebuild_embeddings_cmd
from theo.platform.application import resolve_application
from theo.infrastructure.api.app.persistence_models import Document as DocumentRecord
from theo.infrastructure.api.app.persistence_models import Passage
from theo.adapters.persistence import dispose_sqlite_engine

from tests.integration._db import configure_temporary_engine

pytestmark = pytest.mark.schema


def test_cli_rebuild_embeddings_updates_passages(tmp_path: Path) -> None:
    """Run the CLI against a temporary database and ensure embeddings are written."""

    db_path = tmp_path / "cli.db"
    engine = configure_temporary_engine(db_path)
    resolve_application.cache_clear()
    resolve_application()

    with Session(engine) as session:
        now = datetime.now(timezone.utc)
        record = DocumentRecord(
            id="doc-cli",
            title="Sermon on Genesis",
            collection="sermons",
            created_at=now,
            updated_at=now,
            bib_json={"language": "en"},
        )
        session.add(record)
        session.flush()
        session.add_all(
            [
                Passage(
                    id="p1",
                    document_id=record.id,
                    text="In the beginning God created the heavens and the earth.",
                    raw_text="In the beginning God created the heavens and the earth.",
                    tokens=10,
                ),
                Passage(
                    id="p2",
                    document_id=record.id,
                    text="The earth was without form and void, and darkness covered the deep.",
                    raw_text="The earth was without form and void, and darkness covered the deep.",
                    tokens=16,
                ),
            ]
        )
        session.commit()

    runner = CliRunner()
    result = runner.invoke(rebuild_embeddings_cmd, [])
    assert result.exit_code == 0
    assert "Batch" in result.output
    assert "s/pass" in result.output

    with Session(engine) as session:
        embeddings = session.query(Passage.id, Passage.embedding).filter(
            Passage.id.in_(["p1", "p2"])
        )
        vectors = {row[0]: row[1] for row in embeddings}
        assert set(vectors) == {"p1", "p2"}
        dim = get_settings().embedding_dim
        assert all(isinstance(vector, list) and len(vector) == dim for vector in vectors.values())

    dispose_sqlite_engine(engine)
