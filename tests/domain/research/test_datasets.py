"""Unit tests for research dataset loaders."""
from __future__ import annotations

import pytest

from theo.domain.research import datasets


def test_load_dict_of_dicts_validates_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = {"alpha": {"beta": 1}}

    monkeypatch.setattr(datasets, "_load_json", lambda filename: sample)

    result = datasets._load_dict_of_dicts("sample.json")
    assert result == sample
    assert isinstance(result["alpha"], dict)


def test_load_dict_of_dicts_rejects_invalid_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(datasets, "_load_json", lambda filename: [])
    with pytest.raises(TypeError):
        datasets._load_dict_of_dicts("bad.json")

    monkeypatch.setattr(datasets, "_load_json", lambda filename: {1: {}})
    with pytest.raises(TypeError):
        datasets._load_dict_of_dicts("bad_keys.json")

    monkeypatch.setattr(datasets, "_load_json", lambda filename: {"key": []})
    with pytest.raises(TypeError):
        datasets._load_dict_of_dicts("bad_values.json")


def test_load_dict_of_dict_lists_validates_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = {"alpha": [{"beta": 1}, {"gamma": 2}]}

    monkeypatch.setattr(datasets, "_load_json", lambda filename: sample)

    result = datasets._load_dict_of_dict_lists("sample.json")
    assert result == sample
    assert all(isinstance(entry, dict) for entry in result["alpha"])

    monkeypatch.setattr(datasets, "_load_json", lambda filename: {"alpha": {}})
    with pytest.raises(TypeError):
        datasets._load_dict_of_dict_lists("bad_list.json")

    monkeypatch.setattr(datasets, "_load_json", lambda filename: {"alpha": [1, 2]})
    with pytest.raises(TypeError):
        datasets._load_dict_of_dict_lists("bad_entry.json")


def test_load_list_of_dicts_rejects_non_dict_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = [{"alpha": 1}, {"beta": 2}]

    monkeypatch.setattr(datasets, "_load_json", lambda filename: sample)

    result = datasets._load_list_of_dicts("sample.json")
    assert result == sample
    assert all(isinstance(entry, dict) for entry in result)

    monkeypatch.setattr(datasets, "_load_json", lambda filename: {"not": "a list"})
    with pytest.raises(TypeError):
        datasets._load_list_of_dicts("bad.json")

    monkeypatch.setattr(datasets, "_load_json", lambda filename: [1, 2])
    with pytest.raises(TypeError):
        datasets._load_list_of_dicts("bad_entries.json")


def test_dataset_functions_are_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    datasets.scripture_dataset.cache_clear()
    datasets.crossref_dataset.cache_clear()

    scripture_calls: list[str] = []
    crossref_calls: list[str] = []

    def fake_dict_loader(filename: str) -> dict[str, dict[str, int]]:
        scripture_calls.append(filename)
        return {"alpha": {"beta": 1}}

    def fake_dict_list_loader(filename: str) -> dict[str, list[dict[str, int]]]:
        crossref_calls.append(filename)
        return {"alpha": [{"beta": 1}]}

    monkeypatch.setattr(datasets, "_load_dict_of_dicts", fake_dict_loader)
    monkeypatch.setattr(datasets, "_load_dict_of_dict_lists", fake_dict_list_loader)

    first_scripture = datasets.scripture_dataset()
    second_scripture = datasets.scripture_dataset()
    first_crossref = datasets.crossref_dataset()
    second_crossref = datasets.crossref_dataset()

    assert first_scripture is second_scripture
    assert first_crossref is second_crossref
    assert scripture_calls == ["scripture.json"]
    assert crossref_calls == ["crossrefs.json"]

    datasets.scripture_dataset.cache_clear()
    datasets.crossref_dataset.cache_clear()
