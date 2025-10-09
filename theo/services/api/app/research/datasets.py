"""Embedded starter datasets powering the research endpoints."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

_DATA_PACKAGE = "theo.services.api.app.research.data"


def _load_json(filename: str) -> Any:
    with (
        resources.files(_DATA_PACKAGE)
        .joinpath(filename)
        .open("r", encoding="utf-8")
    ) as handle:
        return json.load(handle)


def _load_dict_of_dicts(filename: str) -> dict[str, dict[str, Any]]:
    data = _load_json(filename)
    if not isinstance(data, dict):  # pragma: no cover - defensive
        raise TypeError(f"Expected dict when loading {filename}")
    typed: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, dict):  # pragma: no cover - defensive
            raise TypeError(f"Unexpected structure in {filename}")
        typed[key] = value
    return typed


def _load_dict_of_dict_lists(filename: str) -> dict[str, list[dict[str, Any]]]:
    data = _load_json(filename)
    if not isinstance(data, dict):  # pragma: no cover - defensive
        raise TypeError(f"Expected dict when loading {filename}")
    typed: dict[str, list[dict[str, Any]]] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, list):  # pragma: no cover - defensive
            raise TypeError(f"Unexpected structure in {filename}")
        entries: list[dict[str, Any]] = []
        for entry in value:
            if not isinstance(entry, dict):  # pragma: no cover - defensive
                raise TypeError(f"Unexpected entry in {filename}")
            entries.append(entry)
        typed[key] = entries
    return typed


def _load_list_of_dicts(filename: str) -> list[dict[str, Any]]:
    data = _load_json(filename)
    if not isinstance(data, list):  # pragma: no cover - defensive
        raise TypeError(f"Expected list when loading {filename}")
    entries: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):  # pragma: no cover - defensive
            raise TypeError(f"Unexpected entry in {filename}")
        entries.append(entry)
    return entries


@lru_cache(maxsize=None)
def scripture_dataset() -> dict[str, dict[str, Any]]:
    """Return the scripture dataset keyed by translation then OSIS."""

    return _load_dict_of_dicts("scripture.json")


@lru_cache(maxsize=None)
def crossref_dataset() -> dict[str, list[dict[str, Any]]]:
    """Return the cross-reference dataset keyed by OSIS."""

    return _load_dict_of_dict_lists("crossrefs.json")


@lru_cache(maxsize=None)
def morphology_dataset() -> dict[str, list[dict[str, Any]]]:
    """Return the morphology dataset keyed by OSIS."""

    return _load_dict_of_dict_lists("morphology.json")


@lru_cache(maxsize=None)
def variants_dataset() -> dict[str, list[dict[str, Any]]]:
    """Return the textual variants dataset keyed by OSIS."""

    return _load_dict_of_dict_lists("variants.json")


@lru_cache(maxsize=None)
def dss_links_dataset() -> dict[str, list[dict[str, Any]]]:
    """Return Dead Sea Scrolls linkage data keyed by OSIS."""

    return _load_dict_of_dict_lists("dss_links.json")


@lru_cache(maxsize=None)
def historicity_dataset() -> list[dict[str, Any]]:
    """Return the historicity dataset containing citation entries."""

    return _load_list_of_dicts("historicity.json")


@lru_cache(maxsize=None)
def fallacy_dataset() -> list[dict[str, Any]]:
    """Return heuristic definitions for fallacy detection."""

    return _load_list_of_dicts("fallacies.json")


@lru_cache(maxsize=None)
def report_templates_dataset() -> dict[str, dict[str, Any]]:
    """Return stance-specific report templates."""

    return _load_dict_of_dicts("report_templates.json")
