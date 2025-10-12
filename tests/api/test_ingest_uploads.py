from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades.database import get_session  # noqa: E402
from theo.services.api.app.main import app  # noqa: E402
from theo.services.api.app.ingest import parsers as ingest_parsers  # noqa: E402
from theo.services.api.app.ingest.pipeline import parse_text_file  # noqa: E402
from theo.services.api.app.routes import ingest as ingest_module  # noqa: E402


@pytest.fixture()
def api_client(api_engine):
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

    def fake_pipeline(
        _session, path: Path, frontmatter, *, dependencies=None
    ) -> object:
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
    captured_paths: dict[str, Path | None] = {}
    captured_filenames: dict[str, str | None] = {}

    def fake_pipeline(
        _session,
        transcript_path: Path,
        frontmatter,
        audio_path: Path | None,
        *,
        transcript_filename: str | None = None,
        audio_filename: str | None = None,
        dependencies=None,
    ) -> object:
        captured_paths["transcript"] = transcript_path
        captured_paths["audio"] = audio_path
        captured_filenames["transcript"] = transcript_filename
        captured_filenames["audio"] = audio_filename
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
            "transcript": ("..\\..\\evil.vtt", b"captions", "text/vtt"),
            "audio": ("C:/temp/uploads/evil.mp3", b"audio-bytes", "audio/mpeg"),
        },
    )

    assert response.status_code == 200
    transcript_path = captured_paths.get("transcript")
    assert isinstance(transcript_path, Path)
    assert transcript_path.parent == tmp_dir
    assert transcript_path.name.endswith("evil.vtt")
    assert transcript_path.resolve().is_relative_to(tmp_dir.resolve())

    audio_path = captured_paths.get("audio")
    assert audio_path is not None
    assert isinstance(audio_path, Path)
    assert audio_path.parent == tmp_dir
    assert audio_path.name.endswith("evil.mp3")
    assert audio_path.resolve().is_relative_to(tmp_dir.resolve())

    assert captured_filenames["transcript"] == "evil.vtt"
    assert captured_filenames["audio"] == "evil.mp3"


def test_ingest_markdown_with_windows_1252_bytes(
    tmp_path: Path, monkeypatch, api_client
) -> None:
    captured: dict[str, str] = {}

    def fake_pipeline(
        _session, path: Path, frontmatter, *, dependencies=None
    ) -> object:
        body, _ = parse_text_file(path)
        captured["body"] = body
        return _mkdoc()

    monkeypatch.setattr(ingest_module, "run_pipeline_for_file", fake_pipeline)

    tmp_dir = tmp_path / "uploads"
    tmp_dir.mkdir()

    monkeypatch.setattr(
        ingest_module.tempfile,
        "mkdtemp",
        lambda *args, **kwargs: str(tmp_dir),
    )

    payload = "Caf\xe9 in Windows-1252".encode("cp1252")
    response = api_client.post(
        "/ingest/file",
        files={"file": ("note.md", payload, "text/markdown")},
    )

    assert response.status_code == 200
    assert "body" in captured
    assert "\ufffd" in captured["body"]


def test_ingest_html_with_windows_1252_bytes(
    tmp_path: Path, monkeypatch, api_client
) -> None:
    captured: dict[str, str] = {}

    def fake_pipeline(
        _session, path: Path, frontmatter, *, dependencies=None
    ) -> object:
        result = ingest_parsers.parse_html_document(path, max_tokens=256)
        captured["text"] = result.text
        return _mkdoc()

    monkeypatch.setattr(ingest_module, "run_pipeline_for_file", fake_pipeline)

    tmp_dir = tmp_path / "uploads"
    tmp_dir.mkdir()

    monkeypatch.setattr(
        ingest_module.tempfile,
        "mkdtemp",
        lambda *args, **kwargs: str(tmp_dir),
    )

    payload = "<html><body><p>Smart quotes: “hello”</p></body></html>".encode("cp1252")
    response = api_client.post(
        "/ingest/file",
        files={"file": ("snippet.html", payload, "text/html")},
    )

    assert response.status_code == 200
    assert "text" in captured
    assert "\ufffd" in captured["text"]
