from __future__ import annotations

import sys
import types

import pytest

from theo.services.api.app.utils.imports import LazyImportModule


def test_lazy_import_module_propagates_attribute_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_name = "tests.lazy_import_module_target"
    module = types.ModuleType(module_name)
    module._discover_items = lambda *a, **k: None  # noqa: ANN001 - test helper

    monkeypatch.setitem(sys.modules, module_name, module)

    proxy = LazyImportModule(module_name)

    replacement = object()
    proxy._discover_items = replacement

    assert module._discover_items is replacement
    assert proxy._discover_items is replacement

    sentinel = object()
    monkeypatch.setattr(proxy, "_discover_items", sentinel)

    assert module._discover_items is sentinel
    assert proxy._discover_items is sentinel

    payload = object()
    proxy.extra_attribute = payload

    assert getattr(module, "extra_attribute") is payload
    assert getattr(proxy, "extra_attribute") is payload

    del proxy.extra_attribute
    assert not hasattr(module, "extra_attribute")

