from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pytest

from theo.domain.research import crossrefs, scripture
from theo.domain.research import datasets as research_datasets


_DATASET_LOADERS = (
    research_datasets.scripture_dataset,
    research_datasets.crossref_dataset,
    research_datasets.morphology_dataset,
    research_datasets.variants_dataset,
    research_datasets.dss_links_dataset,
    research_datasets.historicity_dataset,
    research_datasets.fallacy_dataset,
    research_datasets.report_templates_dataset,
)


@pytest.fixture(autouse=True)
def _reset_dataset_caches() -> Iterable[None]:
    for loader in _DATASET_LOADERS:
        loader.cache_clear()
    yield
    for loader in _DATASET_LOADERS:
        loader.cache_clear()


@pytest.fixture
def mock_dataset_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    def write_json(filename: str, payload: object) -> None:
        (tmp_path / filename).write_text(json.dumps(payload), encoding="utf-8")

    write_json(
        "scripture.json",
        {
            "SBLGNT": {
                "John.1.1": {
                    "text": "In the beginning",
                    "book": "John",
                    "chapter": 1,
                    "verse": 1,
                },
                "John.1.2": {
                    "text": "was the Word",
                    "book": "John",
                    "chapter": 1,
                    "verse": 2,
                },
            },
            "MOCK": {
                "John.1.1": {
                    "text": "Mock In the beginning",
                    "book": "John",
                    "chapter": 1,
                    "verse": 1,
                },
                "John.1.2": {
                    "text": "Mock was the Word",
                    "book": "John",
                    "chapter": 1,
                    "verse": 2,
                },
            },
        },
    )
    write_json(
        "crossrefs.json",
        {
            "John.1.1": [
                {
                    "target": "John.1.2",
                    "weight": 0.9,
                    "relation_type": "parallel",
                    "summary": "Opening parallels",
                    "dataset": "MockAPI",
                }
            ]
        },
    )
    write_json(
        "morphology.json",
        {
            "John.1.1": [
                {
                    "token": "Ἐν",
                    "lemma": "ἐν",
                    "pos": "PREP",
                }
            ]
        },
    )
    write_json(
        "variants.json",
        {
            "John.1.1": [
                {
                    "manuscript": "P66",
                    "reading": "ἐν ἀρχῇ",
                    "confidence": 0.75,
                }
            ]
        },
    )
    write_json(
        "dss_links.json",
        {
            "Isa.7.14": [
                {
                    "fragment": "4QIsa",
                    "link": "https://example.org/dss/4QIsa",
                }
            ]
        },
    )
    write_json(
        "historicity.json",
        [
            {
                "source": "Eusebius",
                "summary": "Attestation of John",
                "year": 320,
            }
        ],
    )
    write_json(
        "fallacies.json",
        [
            {
                "name": "Appeal to Authority",
                "description": "Unsupported citation",
            }
        ],
    )
    write_json(
        "report_templates.json",
        {
            "balanced": {
                "title": "Balanced Overview",
                "sections": ["summary"],
            }
        },
    )

    monkeypatch.setattr(research_datasets, "_DATA_PACKAGE_ROOT", tmp_path)
    return tmp_path


def test_scripture_dataset_uses_mock_provider(mock_dataset_root: Path) -> None:
    data = research_datasets.scripture_dataset()

    assert set(data.keys()) == {"SBLGNT", "MOCK"}
    assert data["SBLGNT"]["John.1.1"]["text"] == "In the beginning"


def test_fetch_passage_integration_with_mock_translation(
    mock_dataset_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scripture, "expand_osis_reference", lambda _: frozenset({1, 2}))
    monkeypatch.setattr(
        scripture,
        "verse_ids_to_osis",
        lambda ids: [f"John.1.{index}" for index in ids],
    )
    monkeypatch.setattr(scripture.pb, "is_valid_verse_id", lambda verse_id: verse_id in {1, 2})

    verses = scripture.fetch_passage("John.1.1-John.1.2", translation="mock")

    assert [verse.osis for verse in verses] == ["John.1.1", "John.1.2"]
    assert {verse.translation for verse in verses} == {"MOCK"}
    assert verses[0].text == "Mock In the beginning"


def test_cross_reference_transformation(mock_dataset_root: Path) -> None:
    entries = crossrefs.fetch_cross_references("John.1.1")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.target == "John.1.2"
    assert entry.dataset == "MockAPI"
    assert entry.weight == pytest.approx(0.9)


def test_crossref_dataset_validates_structure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "crossrefs.json").write_text(json.dumps(["invalid"]), encoding="utf-8")
    monkeypatch.setattr(research_datasets, "_DATA_PACKAGE_ROOT", tmp_path)

    with pytest.raises(TypeError, match="Expected dict when loading crossrefs.json"):
        research_datasets.crossref_dataset()


def test_fetch_passage_missing_data_raises(mock_dataset_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scripture, "expand_osis_reference", lambda _: frozenset())

    with pytest.raises(KeyError, match="No scripture data available for 'John.9.9'"):
        scripture.fetch_passage("John.9.9", translation="mock")


def test_crossref_dataset_cache_invalidation(mock_dataset_root: Path) -> None:
    first = research_datasets.crossref_dataset()
    again = research_datasets.crossref_dataset()

    assert again is first

    (mock_dataset_root / "crossrefs.json").write_text(
        json.dumps({"John.1.1": [{"target": "John.1.3"}]}),
        encoding="utf-8",
    )

    research_datasets.crossref_dataset.cache_clear()
    refreshed = research_datasets.crossref_dataset()

    assert refreshed is not first
    assert refreshed["John.1.1"][0]["target"] == "John.1.3"
