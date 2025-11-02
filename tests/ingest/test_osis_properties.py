"""Property tests validating OSIS helpers in the ingest pipeline."""

from __future__ import annotations

import importlib
import sys
import types

import pythonbible as pb
import pytest
from hypothesis import given

from tests.fixtures.strategies import (
    DEFAULT_HYPOTHESIS_SETTINGS,
    normalized_osis_references,
)

if "fastapi" not in sys.modules:
    fastapi_module = types.ModuleType("fastapi")
    status_module = types.SimpleNamespace(HTTP_422_UNPROCESSABLE_CONTENT=422)
    fastapi_module.status = status_module  # type: ignore[attr-defined]
    sys.modules["fastapi"] = fastapi_module
    sys.modules["fastapi.status"] = status_module

pytest.importorskip("pythonbible")

legacy_services = importlib.import_module("theo.services")
osis_module = importlib.import_module("theo.infrastructure.api.app.ingest.osis")


def _register_legacy_submodule(name: str, module: types.ModuleType) -> None:
    """Expose *module* under ``theo.services.api.app.ingest`` for compatibility."""

    api_pkg = getattr(legacy_services, "api", None)
    if api_pkg is None:
        api_pkg = types.ModuleType("theo.services.api")
        api_pkg.__path__ = []  # type: ignore[attr-defined]
        setattr(legacy_services, "api", api_pkg)
        sys.modules["theo.services.api"] = api_pkg
    app_pkg = getattr(api_pkg, "app", None)
    if app_pkg is None:
        app_pkg = types.ModuleType("theo.services.api.app")
        app_pkg.__path__ = []  # type: ignore[attr-defined]
        setattr(api_pkg, "app", app_pkg)
        sys.modules["theo.services.api.app"] = app_pkg
    ingest_pkg = getattr(app_pkg, "ingest", None)
    if ingest_pkg is None:
        ingest_pkg = types.ModuleType("theo.services.api.app.ingest")
        ingest_pkg.__path__ = []  # type: ignore[attr-defined]
        setattr(app_pkg, "ingest", ingest_pkg)
        sys.modules["theo.services.api.app.ingest"] = ingest_pkg

    setattr(ingest_pkg, name, module)
    sys.modules[f"theo.services.api.app.ingest.{name}"] = module


_register_legacy_submodule("osis", osis_module)

from theo.services.api.app.ingest import osis as legacy_osis  # noqa: E402


@given(normalized_osis_references())
@DEFAULT_HYPOTHESIS_SETTINGS
def test_expand_and_combine_round_trip(reference: pb.NormalizedReference) -> None:
    """OSIS helpers round-trip canonical references without data loss."""

    osis_value = legacy_osis.format_osis(reference)
    assert legacy_osis.canonicalize_osis_id(osis_value) == osis_value

    verse_ids = legacy_osis.expand_osis_reference(osis_value)
    assert verse_ids, "Round-trip expansion should produce verse identifiers"

    sorted_ids = sorted(verse_ids)
    reconstructed = [
        pb.convert_verse_ids_to_references([verse_id])[0] for verse_id in sorted_ids
    ]

    combined = legacy_osis.combine_references(reconstructed)
    if combined is not None:
        assert legacy_osis.format_osis(combined) == osis_value

    canonical_ids, start_id, end_id = legacy_osis.canonical_verse_range([osis_value])
    assert canonical_ids is not None
    assert canonical_ids == sorted_ids
    assert start_id == sorted_ids[0]
    assert end_id == sorted_ids[-1]

    readable = legacy_osis.osis_to_readable(osis_value)
    detected = legacy_osis.detect_osis_references(f"Study {readable} in context")
    assert osis_value in detected.all

    for ref in reconstructed:
        verse_osis = legacy_osis.format_osis(ref)
        assert legacy_osis.osis_intersects(verse_osis, osis_value)
