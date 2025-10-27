"""Tests for the ``theo.infrastructure.api.app.ingest`` package initialisation."""

from __future__ import annotations

import types

import pytest

import theo.infrastructure.api.app.ingest as ingest


def test_ingest_package_exports_are_loaded_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    """Accessing exported attributes triggers a deferred import of ``tei_pipeline``."""

    sentinel = object()
    stub_module = types.SimpleNamespace(HTRResult=sentinel)
    captured: list[tuple[str, str | None]] = []

    def fake_import_module(name: str, package: str | None = None):
        captured.append((name, package))
        return stub_module

    monkeypatch.setattr(ingest, "import_module", fake_import_module)

    result = ingest.__getattr__("HTRResult")

    assert result is sentinel
    assert captured == [(".tei_pipeline", ingest.__name__)]


def test_ingest_package_raises_for_unknown_attribute() -> None:
    """Unexpected attribute lookups raise :class:`AttributeError`."""

    with pytest.raises(AttributeError):
        ingest.__getattr__("unknown")


def test_ingest_package_dir_includes_reexports() -> None:
    """``dir()`` exposes the re-exported helper names for introspection."""

    entries = ingest.__dir__()

    for name in ("HTRClientProtocol", "generate_tei_markup"):
        assert name in entries
