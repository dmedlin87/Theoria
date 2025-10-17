"""Tests for the OSIS commentary import workflow."""

from __future__ import annotations

import sys
from textwrap import dedent
from pathlib import Path

from click.testing import CliRunner
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
    get_settings,
)
from theo.adapters.persistence.models import CommentaryExcerptSeed  # noqa: E402
from theo.services.api.app.ingest.pipeline import (  # noqa: E402
    PipelineDependencies,
    import_osis_commentary,
)
from theo.services.cli import ingest_osis as cli  # noqa: E402


def _prepare_db(tmp_path: Path) -> None:
    db_path = tmp_path / "osis.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _write_sample_osis(path: Path, *, updated: bool = False) -> None:
    first_comment = "Updated insight on the Word." if updated else "Initial insight on the Word."
    payload = dedent(
        f"""
        <osis>
          <osisText osisIDWork="Commentary.Work">
            <div type="commentary">
              <verse osisID="John.1.1">In the beginning was the Word.
                <note type="commentary" osisRef="John.1.1">{first_comment}</note>
              </verse>
              <verse osisID="John.1.2 John.1.3">He was with God in the beginning.
                <note type="commentary" osisRef="John.1.2 John.1.3">
                  Shared reflection on these verses.
                </note>
              </verse>
            </div>
          </osisText>
        </osis>
        """
    ).strip()
    path.write_text(payload, encoding="utf-8")


def test_import_osis_commentary_persists_entries(tmp_path: Path) -> None:
    _prepare_db(tmp_path)
    engine = get_engine()
    osis_path = tmp_path / "commentary.xml"
    _write_sample_osis(osis_path)

    settings = get_settings()
    dependencies = PipelineDependencies(settings=settings)
    frontmatter = {
        "source": "Test Source",
        "perspective": "Devotional",
        "tags": ["alpha", "beta"],
    }

    with Session(engine) as session:
        result = import_osis_commentary(
            session,
            osis_path,
            frontmatter=frontmatter,
            dependencies=dependencies,
        )

    assert result.inserted == 3
    assert result.updated == 0
    assert result.skipped == 0

    with Session(engine) as session:
        rows = (
            session.query(CommentaryExcerptSeed)
            .order_by(CommentaryExcerptSeed.osis.asc())
            .all()
        )

    assert [row.osis for row in rows] == ["John.1.1", "John.1.2", "John.1.3"]
    assert all(row.source == "Test Source" for row in rows)
    assert all(row.perspective == "devotional" for row in rows)
    assert rows[0].tags == ["alpha", "beta"]
    assert rows[0].excerpt.startswith("Initial insight")


def test_import_osis_commentary_merges_updates(tmp_path: Path) -> None:
    _prepare_db(tmp_path)
    engine = get_engine()
    osis_path = tmp_path / "commentary.xml"
    _write_sample_osis(osis_path)

    settings = get_settings()
    dependencies = PipelineDependencies(settings=settings)

    with Session(engine) as session:
        import_osis_commentary(
            session,
            osis_path,
            frontmatter={"source": "Seed", "perspective": "Neutral"},
            dependencies=dependencies,
        )

    _write_sample_osis(osis_path, updated=True)

    with Session(engine) as session:
        result = import_osis_commentary(
            session,
            osis_path,
            frontmatter={"source": "Seed", "perspective": "Neutral"},
            dependencies=dependencies,
        )

    assert result.inserted == 0
    assert result.updated == 1
    assert result.skipped == 2

    with Session(engine) as session:
        refreshed = (
            session.query(CommentaryExcerptSeed)
            .filter(CommentaryExcerptSeed.osis == "John.1.1")
            .one()
        )
    assert refreshed.excerpt.startswith("Updated insight")


def test_cli_ingest_osis_reports_summary(tmp_path: Path) -> None:
    osis_path = tmp_path / "cli_commentary.xml"
    _write_sample_osis(osis_path)

    database_url = f"sqlite:///{tmp_path / 'cli.db'}"
    runner = CliRunner()
    result = runner.invoke(
        cli.ingest_osis,
        [
            str(osis_path),
            "--source",
            "CLI Source",
            "--perspective",
            "Historical",
            "--tag",
            "cli",
            "--database",
            database_url,
        ],
    )

    assert result.exit_code == 0
    assert "Imported 3 new commentary excerpts" in result.output

    configure_engine(database_url)
    engine = get_engine()
    with Session(engine) as session:
        records = session.query(CommentaryExcerptSeed).all()
    assert len(records) == 3
    assert all(record.source == "CLI Source" for record in records)
    assert all(record.perspective == "historical" for record in records)
    assert records[0].tags == ["cli"]
