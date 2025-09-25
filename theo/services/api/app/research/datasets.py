"""Embedded starter datasets powering the research endpoints."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

_DATA_PACKAGE = "theo.services.api.app.research.data"


def _load_json(filename: str) -> Any:
    with resources.files(_DATA_PACKAGE).joinpath(filename).open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=None)
def scripture_dataset() -> dict[str, dict[str, Any]]:
    """Return the scripture dataset keyed by translation then OSIS."""

    return _load_json("scripture.json")


@lru_cache(maxsize=None)
def crossref_dataset() -> dict[str, list[dict[str, Any]]]:
    """Return the cross-reference dataset keyed by OSIS."""

    return _load_json("crossrefs.json")


@lru_cache(maxsize=None)
def morphology_dataset() -> dict[str, list[dict[str, Any]]]:
    """Return the morphology dataset keyed by OSIS."""

    return _load_json("morphology.json")
