"""Unit tests for citation export helper functions."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from theo.services.api.app.export.citations import (
    _apa_author,
    _chicago_author,
    _format_anchor_summary,
    _join_with_and,
    _normalise_author,
    _sbl_author,
    _extract_passages,
)


@pytest.mark.parametrize(
    "values, expected",
    [
        ([], ""),
        (["Paul"], "Paul"),
        (["Paul", "Barnabas"], "Paul and Barnabas"),
        (["Paul", "Barnabas", "Silas"], "Paul, Barnabas, and Silas"),
        (["  Paul  ", "", "Barnabas"], "Paul and Barnabas"),
    ],
)
def test_join_with_and_trims_and_formats(values: list[str], expected: str) -> None:
    assert _join_with_and(values) == expected


def test_join_with_and_allows_disabling_oxford_comma() -> None:
    assert (
        _join_with_and(["Paul", "Barnabas", "Silas"], use_oxford_comma=False)
        == "Paul, Barnabas and Silas"
    )


def test_format_anchor_summary_combines_available_fields() -> None:
    anchors = [
        {"osis": "John.1.1", "label": "Prologue"},
        {"osis": "Acts.2.1", "anchor": "Pentecost"},
        {"label": "Sermon on the Mount"},
        {"osis": "Luke.2.1"},
        {"anchor": "General Epistles"},
    ]

    summary = _format_anchor_summary(anchors)

    assert summary == (
        "John.1.1 (Prologue); Acts.2.1 (Pentecost); Sermon on the Mount; "
        "Luke.2.1; General Epistles"
    )


@dataclass
class AttrPassage:
    id: str
    document_id: str
    osis_ref: str
    text: str
    page_no: int | None = None
    t_start: float | None = None
    t_end: float | None = None
    meta: dict[str, str] | None = None


class DumpablePassage:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def model_dump(self, *, mode: str = "json") -> dict[str, object]:
        return {**self._payload, "mode": mode}


def test_extract_passages_serialises_supported_shapes() -> None:
    mapping_source = {
        "passages": [
            {"id": "p1", "text": "In the beginning"},
            DumpablePassage({"id": "p2", "text": "was the Word"}),
            AttrPassage(
                id="p3",
                document_id="doc-3",
                osis_ref="John.1.1",
                text="and the Word was with God",
            ),
        ]
    }

    serialised = _extract_passages(mapping_source)

    assert serialised is not None
    assert serialised[0] == {"id": "p1", "text": "In the beginning"}
    assert serialised[1] == {"id": "p2", "text": "was the Word", "mode": "json"}
    third = serialised[2]
    assert third["id"] == "p3"
    assert third["document_id"] == "doc-3"
    assert third["osis_ref"] == "John.1.1"
    assert third["text"] == "and the Word was with God"
    assert third["page_no"] is None


def test_extract_passages_handles_object_source() -> None:
    class Container:
        def __init__(self, passages: list[object]) -> None:
            self.passages = passages

    container = Container(
        passages=[
            {"id": "p4", "text": "and the Word was God"},
        ]
    )

    serialised = _extract_passages(container)

    assert serialised == [{"id": "p4", "text": "and the Word was God"}]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Doe, Jane M.", {"given": "Jane M.", "family": "Doe"}),
        ("Jane Mary Doe", {"given": "Jane Mary", "family": "Doe"}),
        (
            "United States Census Bureau",
            {"literal": "United States Census Bureau"},
        ),
        ("UNITED NATIONS", {"literal": "UNITED NATIONS"}),
        ("JOHN DOE", {"given": "JOHN", "family": "DOE"}),
        ("Single", {"literal": "Single"}),
        ("", {"literal": ""}),
    ],
)
def test_normalise_author_handles_varied_inputs(raw: str, expected: dict[str, str]) -> None:
    assert _normalise_author(raw) == expected


@pytest.mark.parametrize(
    "author, expected",
    [
        ({"family": "Doe", "given": "Jane Mary"}, "Doe, J. M."),
        ({"family": "Doe"}, "Doe"),
        ({"literal": "Psalmist"}, "Psalmist"),
    ],
)
def test_apa_author_formats_expected_output(author: dict[str, str], expected: str) -> None:
    assert _apa_author(author) == expected


@pytest.mark.parametrize(
    "author, expected",
    [
        ({"family": "Doe", "given": "John"}, "Doe, John"),
        ({"family": "Doe"}, "Doe"),
        ({"literal": "Editorial Board"}, "Editorial Board"),
    ],
)
def test_chicago_author_formats_expected_output(author: dict[str, str], expected: str) -> None:
    assert _chicago_author(author) == expected


@pytest.mark.parametrize(
    "author, primary, expected",
    [
        ({"family": "Doe", "given": "Jane"}, True, "Doe, Jane"),
        ({"family": "Doe", "given": "Jane"}, False, "Jane Doe"),
        ({"literal": "Unknown"}, True, "Unknown"),
    ],
)
def test_sbl_author_formats_expected_output(
    author: dict[str, str], primary: bool, expected: str
) -> None:
    assert _sbl_author(author, primary=primary) == expected
