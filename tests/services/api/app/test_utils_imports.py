"""Tests for lazy import utilities."""

from types import ModuleType

import pytest

from theo.infrastructure.api.app.utils import imports


class SentinelError(RuntimeError):
    """Raised when an unexpected import occurs during a test."""


def test_lazy_import_load_caches_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loading multiple times should only import the module once."""

    imported_module = ModuleType("tests.fake.module")
    calls: list[str] = []

    def fake_import(dotted_path: str) -> ModuleType:
        calls.append(dotted_path)
        return imported_module

    monkeypatch.setattr(imports, "import_module", fake_import)
    proxy = imports.LazyImportModule("tests.fake.module")

    first = proxy.load()
    second = proxy.load()

    assert first is imported_module
    assert second is imported_module
    assert calls == ["tests.fake.module"], "module should be imported only once"


def test_lazy_import_setattr_forwards_to_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting attributes on the proxy should update the real module."""

    imported_module = ModuleType("tests.fake.module")

    monkeypatch.setattr(imports, "import_module", lambda _path: imported_module)
    proxy = imports.LazyImportModule("tests.fake.module")

    proxy.dynamic = "value"

    assert getattr(imported_module, "dynamic") == "value"


def test_lazy_import_internal_attr_assignment_does_not_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assigning internal attributes should not trigger an import."""

    proxy = imports.LazyImportModule("tests.fake.module")
    monkeypatch.setattr(
        imports,
        "import_module",
        lambda _path: (_ for _ in ()).throw(SentinelError()),
    )

    sentinel = object()
    proxy._module = sentinel

    assert proxy._module is sentinel
