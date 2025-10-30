"""Tests ensuring export identifiers remain deterministic."""

from __future__ import annotations

from uuid import UUID

from theo.infrastructure.api.app.export import formatters


def test_generate_export_id_uses_uuid4(monkeypatch) -> None:
    fake_uuid = UUID("12345678-1234-5678-1234-567812345678")

    monkeypatch.setattr(formatters, "uuid4", lambda: fake_uuid)

    assert formatters.generate_export_id() == str(fake_uuid)


def test_build_manifest_respects_supplied_export_id(monkeypatch) -> None:
    calls = []

    def _sentinel() -> str:
        calls.append("called")
        return "unexpected"

    monkeypatch.setattr(formatters, "generate_export_id", _sentinel)

    manifest = formatters.build_manifest(
        export_type="search",
        filters={"query": "logos"},
        totals={"results": 5},
        cursor="cursor-1",
        next_cursor=None,
        mode="results",
        enrichment_version=7,
        export_id="evidence-export",
    )

    assert manifest.export_id == "evidence-export"
    assert calls == []
    assert manifest.schema_version == formatters.SCHEMA_VERSION
