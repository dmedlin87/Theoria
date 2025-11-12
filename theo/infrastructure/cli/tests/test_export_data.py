"""Unit tests for :mod:`theo.infrastructure.cli.export_data` helpers."""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.infrastructure.api.app.models.export import ExportManifest


class _StubRegistry:
    """Minimal adapter registry exposing the engine dependency."""

    def __init__(self) -> None:
        self._engine = object()

    def resolve(self, key: str):  # pragma: no cover - trivial delegation
        if key == "engine":
            return self._engine
        raise KeyError(key)


@pytest.fixture()
def export_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    """Import the CLI module with its bootstrap patched for testing."""

    module_name = "theo.infrastructure.cli.export_data"

    registry = _StubRegistry()
    monkeypatch.setattr(
        "theo.application.services.bootstrap.resolve_application",
        lambda: (object(), registry),
    )

    def install_stub(name: str, attributes: dict[str, object]) -> None:
        module = ModuleType(name)
        for attr, value in attributes.items():
            setattr(module, attr, value)
        monkeypatch.setitem(sys.modules, name, module)

    install_stub(
        "theo.adapters.persistence.models",
        {"Document": type("Document", (), {})},
    )
    install_stub(
        "theo.infrastructure.api.app.export.citations",
        {
            "build_citation_export": lambda *a, **k: (
                SimpleNamespace(export_id="stub", model_dump=lambda **_: {}),
                [],
                None,
            ),
            "render_citation_markdown": lambda manifest, records: "",
        },
    )
    install_stub(
        "theo.infrastructure.api.app.export.formatters",
        {
            "build_document_export": lambda *a, **k: (
                SimpleNamespace(export_id="doc", totals={}),
                [],
            ),
            "build_search_export": lambda *a, **k: (
                SimpleNamespace(export_id="search", totals={}),
                [],
            ),
            "generate_export_id": lambda: "generated-id",
            "render_bundle": lambda manifest, records, output_format=None: ("", {}),
        },
    )
    install_stub(
        "theo.infrastructure.api.app.models.search",
        {
            "HybridSearchFilters": type(
                "HybridSearchFilters", (), {"__init__": lambda self, **kwargs: setattr(self, "data", kwargs)}
            ),
            "HybridSearchRequest": type(
                "HybridSearchRequest", (), {"__init__": lambda self, **kwargs: setattr(self, "data", kwargs)}
            ),
        },
    )
    install_stub(
        "theo.infrastructure.api.app.retriever.export",
        {
            "export_documents": lambda *a, **k: [],
            "export_search_results": lambda *a, **k: SimpleNamespace(results=[]),
        },
    )
    install_stub(
        "theo.infrastructure.api.app.retriever.verses",
        {"get_mentions_for_osis": lambda *a, **k: []},
    )
    install_stub(
        "theo.infrastructure.api.app.models.verses",
        {
            "VerseMentionsFilters": type(
                "VerseMentionsFilters", (), {"__init__": lambda self, **kwargs: setattr(self, "data", kwargs)}
            ),
        },
    )

    if module_name in sys.modules:
        del sys.modules[module_name]
    module = import_module(module_name)
    module.STATE_DIR = tmp_path / "state"
    return module


def test_parse_fields_normalises_input(export_module) -> None:
    """Whitespace and duplicate field names are cleaned before use."""

    mod = export_module
    assert mod._parse_fields(None) is None
    assert mod._parse_fields("") is None
    assert mod._parse_fields("  ,  ") is None

    parsed = mod._parse_fields("title, score , title,  snippet  ")
    assert parsed == {"title", "score", "snippet"}


def test_load_saved_cursor_handles_missing_and_invalid(export_module) -> None:
    """Cursor state is ignored when files are missing or malformed."""

    mod = export_module
    assert mod._load_saved_cursor("unknown") is None

    path = mod._state_path("example")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert mod._load_saved_cursor("example") is None

    path.write_text(json.dumps({"next_cursor": "cursor-123"}), encoding="utf-8")
    assert mod._load_saved_cursor("example") == "cursor-123"


def test_persist_state_writes_manifest_snapshot(export_module) -> None:
    """Persisted manifests are serialised with a trailing newline for readability."""

    mod = export_module
    manifest = ExportManifest(
        export_id="export-1",
        schema_version="1.0",
        created_at=datetime.now(timezone.utc),
        type="search",
        filters={"query": "alpha"},
        totals={"returned": 3},
        next_cursor="cursor-456",
    )

    mod._persist_state(manifest)

    path = mod._state_path(manifest.export_id)
    contents = path.read_text(encoding="utf-8")
    assert contents.endswith("\n")

    data = json.loads(contents)
    assert data["export_id"] == manifest.export_id
    assert data["next_cursor"] == manifest.next_cursor
    assert data["totals"] == manifest.totals


def test_flatten_passages_expands_records(export_module) -> None:
    """Only valid passage collections are expanded into flattened rows."""

    mod = export_module
    records = [
        OrderedDict(
            [
                ("document_id", "doc-1"),
                ("title", "Sample"),
                ("collection", "sermons"),
                ("source_type", "sermon"),
                (
                    "passages",
                    [
                        {
                            "id": "p1",
                            "osis_ref": "John.3.16",
                            "page_no": 2,
                            "meta": {"section": "Intro"},
                        },
                        {
                            "id": "p2",
                            "osis_ref": "John.3.17",
                            "t_start": 10.5,
                            "t_end": 12.9,
                        },
                    ],
                ),
            ]
        ),
        OrderedDict([("passages", "not-a-sequence")]),
        OrderedDict([("document_id", "doc-2")]),
    ]

    flattened = mod._flatten_passages(records)
    assert [entry["passage_id"] for entry in flattened] == ["p1", "p2"]

    first = flattened[0]
    assert first["kind"] == "passage"
    assert first["document_id"] == "doc-1"
    assert first["osis_ref"] == "John.3.16"
    assert first["page_no"] == 2
    assert first["meta"] == {"section": "Intro"}


def test_format_anchor_label_prefers_pages_and_timecodes(export_module) -> None:
    """Anchor labels favour page numbers before falling back to timestamps."""

    mod = export_module

    class Passage:
        def __init__(self, page_no=None, t_start=None, t_end=None) -> None:
            self.page_no = page_no
            self.t_start = t_start
            self.t_end = t_end

    assert mod._format_anchor_label(Passage(page_no=5)) == "p.5"
    assert mod._format_anchor_label(Passage(t_start=14.2, t_end=20.8)) == "14-20s"
    assert mod._format_anchor_label(Passage(t_start=9.0)) == "9s"
    assert mod._format_anchor_label(Passage()) is None
