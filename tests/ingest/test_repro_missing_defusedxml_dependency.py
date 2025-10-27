from __future__ import annotations

import importlib
import sys


def test_repro_missing_defusedxml_dependency(monkeypatch):
    """Importing parsers should not depend on the optional ``defusedxml`` package."""

    for name in list(sys.modules):
        if name.startswith("defusedxml"):
            monkeypatch.delitem(sys.modules, name, raising=False)

    module_name = "theo.infrastructure.api.app.ingest.parsers"
    monkeypatch.delitem(sys.modules, module_name, raising=False)

    parsers = importlib.import_module(module_name)

    # The module should expose a ``DefusedXmlException`` even without ``defusedxml``.
    assert hasattr(parsers, "DefusedXmlException")

    # Malicious XML payloads should still be rejected to prevent XXE tricks.
    malicious = """<?xml version='1.0'?><!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><foo/>"""

    try:
        parsers.ET.fromstring(malicious)
    except parsers.DefusedXmlException:
        pass
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Unsafe XML payload should be rejected")
