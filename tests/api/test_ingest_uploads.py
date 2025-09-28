from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.database import get_session  # noqa: E402
from theo.services.api.app.main import app  # noqa: E402
from theo.services.api.app.routes import ingest as ingest_module  # noqa: E402


@pytest.fixture()
def api_client():
    def _override_session():
        yield object()

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


def _mkdoc(document_id: str = "doc"):
    class _Doc:
        id = document_id

    return _Doc()


def test_ingest_file_sanitizes_uploaded_filename(tmp_path: Path, monkeypatch, api_client):
    captured: dict[str, Path] = {}

    def fake_pipeline(_session, path: Path, frontmatter):
        captured["path"] = path
        return _mkdoc()

    monkeypatch.setattr(ingest_module, "run_pipeline_for_file", fake_pipeline)

    tmp_dir = tmp_path / "uploads"
    tmp_dir.mkdir()

    monkeypatch.setattr(
        ingest_module.tempfile,
        "mkdtemp",
        lambda *args, **kwargs: str(tmp_dir),
    )

    response = api_client.post(
        "/ingest/file",
        files={"file": ("../../evil.txt", b"payload", "text/plain")},
    )

    assert response.status_code == 200
    assert "path" in captured

    stored_path = Path(captured["path"])
    assert stored_path.parent == tmp_dir
    assert stored_path.name.endswith("evil.txt")
    assert stored_path.resolve().is_relative_to(tmp_dir.resolve())


def test_ingest_transcript_sanitizes_uploaded_files(
    tmp_path: Path, monkeypatch, api_client
) -> None:
    captured: dict[str, Path | None] = {}

    def fake_pipeline(
        _session,
        transcript_path: Path,
        frontmatter,
        audio_path: Path | None,
        *,
        transcript_filename: str | None = None,
        audio_filename: str | None = None,
    ):
        captured["transcript"] = transcript_path
        captured["audio"] = audio_path
        captured["transcript_filename"] = transcript_filename
        captured["audio_filename"] = audio_filename
        return _mkdoc()

    monkeypatch.setattr(
        ingest_module, "run_pipeline_for_transcript", fake_pipeline
    )

    tmp_dir = tmp_path / "uploads"
    tmp_dir.mkdir()

    monkeypatch.setattr(
        ingest_module.tempfile,
        "mkdtemp",
        lambda *args, **kwargs: str(tmp_dir),
    )

    response = api_client.post(
        "/ingest/transcript",
        files={
            "transcript": ("../../evil.vtt", b"captions", "text/vtt"),
            "audio": ("../../evil.mp3", b"audio-bytes", "audio/mpeg"),
        },
    )

    assert response.status_code == 200
    transcript_path = Path(captured["transcript"])
    assert transcript_path.parent == tmp_dir
    assert transcript_path.name.endswith("evil.vtt")
    assert transcript_path.resolve().is_relative_to(tmp_dir.resolve())

    audio_path = captured.get("audio")
    assert audio_path is not None
    audio_path = Path(audio_path)
    assert audio_path.parent == tmp_dir
    assert audio_path.name.endswith("evil.mp3")
    assert audio_path.resolve().is_relative_to(tmp_dir.resolve())
