from __future__ import annotations

from unittest.mock import patch

from theo.domain.research import variants_apparatus


def test_variants_apparatus_handles_cross_chapter_ranges() -> None:
    fake_dataset = {
        "Gen.1.31": [
            {
                "id": "gen131",
                "reading": "start",
                "category": "note",
            }
        ],
        "Gen.2.1": [
            {
                "id": "gen21",
                "reading": "middle",
                "category": "note",
            }
        ],
        "Gen.2.2": [
            {
                "id": "gen22",
                "reading": "end",
                "category": "note",
            }
        ],
    }

    with patch("theo.domain.research.variants.variants_dataset", return_value=fake_dataset):
        entries = variants_apparatus("Gen.1.31-Gen.2.2")

    assert [entry.id for entry in entries] == ["gen131", "gen21", "gen22"]
