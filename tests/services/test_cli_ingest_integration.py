from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from theo.services.cli.ingest_folder import IngestItem, _ingest_batch_via_api


class DummySession:
    def __init__(self, engine: object) -> None:
        self.engine = engine
        self.closed = False

    def __enter__(self) -> "DummySession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        self.closed = True

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


@pytest.fixture()
def patched_ingest_environment(monkeypatch: pytest.MonkeyPatch):
    engine = object()
    monkeypatch.setattr("theo.services.cli.ingest_folder.get_engine", lambda: engine)

    session_records: list[DummySession] = []

    def session_factory(bound_engine: object) -> DummySession:
        session = DummySession(bound_engine)
        session_records.append(session)
        return session

    monkeypatch.setattr("theo.services.cli.ingest_folder.Session", session_factory)

    file_calls: list[tuple[object, Path, dict[str, object], object]] = []
    url_calls: list[tuple[object, str, str, dict[str, object], object]] = []

    def fake_file(session: object, path: Path, frontmatter: dict[str, object], *, dependencies: object) -> SimpleNamespace:
        file_calls.append((session, path, dict(frontmatter), dependencies))
        return SimpleNamespace(id=f"file:{path.name}")

    def fake_url(session: object, url: str, *, source_type: str, frontmatter: dict[str, object], dependencies: object) -> SimpleNamespace:
        url_calls.append((session, url, source_type, dict(frontmatter), dependencies))
        return SimpleNamespace(id=f"url:{url}")

    monkeypatch.setattr("theo.services.cli.ingest_folder.run_pipeline_for_file", fake_file)
    monkeypatch.setattr("theo.services.cli.ingest_folder.run_pipeline_for_url", fake_url)

    post_calls: list[tuple[object, list[str]]] = []
    monkeypatch.setattr(
        "theo.services.cli.ingest_folder.POST_BATCH_HANDLERS",
        {"tags": lambda session, documents: post_calls.append((session, list(documents)))}
    )

    class Env(SimpleNamespace):
        pass

    return Env(
        engine=engine,
        sessions=session_records,
        file_calls=file_calls,
        url_calls=url_calls,
        post_calls=post_calls,
    )


def test_ingest_batch_via_api_routes_items(patched_ingest_environment):
    dependencies = object()
    items = [
        IngestItem(path=Path("local.txt"), source_type="txt"),
        IngestItem(url="https://example.test", source_type="web_page"),
    ]

    document_ids = _ingest_batch_via_api(
        items,
        overrides={"collection": "uploads"},
        post_batch_steps={"tags"},
        dependencies=dependencies,
    )

    assert document_ids == ["file:local.txt", "url:https://example.test"]
    assert len(patched_ingest_environment.sessions) == 1
    session = patched_ingest_environment.sessions[0]
    assert session.engine is patched_ingest_environment.engine
    assert session.closed is True

    file_call = patched_ingest_environment.file_calls[0]
    assert file_call[1].name == "local.txt"
    assert file_call[2]["collection"] == "uploads"
    assert file_call[3] is dependencies

    url_call = patched_ingest_environment.url_calls[0]
    assert url_call[1] == "https://example.test"
    assert url_call[2] == "web_page"
    assert url_call[3]["collection"] == "uploads"
    assert url_call[4] is dependencies

    assert patched_ingest_environment.post_calls == [(session, document_ids)]
