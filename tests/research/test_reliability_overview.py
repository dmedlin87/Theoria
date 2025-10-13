import pytest

from theo.domain.research.entities import ResearchNote, ResearchNoteEvidence
from theo.domain.research.overview import (
    _extract_citations,
    _first_sentence,
    _manuscript_bullets,
    _note_to_bullet,
    _summarize_manuscript,
    build_reliability_overview,
)
from theo.domain.research.variants import VariantEntry


def _make_note(
    *,
    note_id: str,
    stance: str | None,
    title: str | None,
    body: str,
    evidences: tuple[ResearchNoteEvidence, ...] = (),
) -> ResearchNote:
    return ResearchNote(
        id=note_id,
        osis="John.3.16",
        stance=stance,
        title=title,
        body=body,
        evidences=evidences,
    )


def _make_evidence(*, evidence_id: str, citation: str | None, source_ref: str | None) -> ResearchNoteEvidence:
    return ResearchNoteEvidence(
        id=evidence_id,
        citation=citation,
        source_ref=source_ref,
    )


def _make_variant(
    *,
    entry_id: str,
    witness: str | None,
    reading: str,
    note: str | None,
    source: str | None,
) -> VariantEntry:
    return VariantEntry(
        id=entry_id,
        osis="John.3.16",
        category="note",
        reading=reading,
        note=note,
        source=source,
        witness=witness,
        translation=None,
        confidence=None,
        dataset=None,
        disputed=None,
        witness_metadata=None,
    )


def test_build_reliability_overview_orders_by_stance_and_limits():
    supportive_evidences = (
        _make_evidence(evidence_id="e1", citation="Smith 2020", source_ref="Smith 2020"),
        _make_evidence(evidence_id="e2", citation="", source_ref="Archive A"),
        _make_evidence(evidence_id="e3", citation="Extra Source", source_ref="Archive A"),
    )
    supportive_note = _make_note(
        note_id="supportive",
        stance="supportive",
        title="Supportive note title. Additional detail follows.",
        body="Supportive body text",
        evidences=supportive_evidences,
    )
    supportive_extra = _make_note(
        note_id="supportive-extra",
        stance="pro",
        title=None,
        body="Second supportive point explained with more detail",
    )
    critical_note = _make_note(
        note_id="critical",
        stance="critical",
        title="Critical claim? Additional context after question.",
        body="Critical body text",
    )
    neutral_note = _make_note(
        note_id="neutral",
        stance="neutral",
        title=None,
        body="Neutral perspective outlining context",
    )
    empty_note = _make_note(
        note_id="empty",
        stance="supportive",
        title=" ",
        body="",
    )

    variants = [
        _make_variant(
            entry_id="v1",
            witness="Codex Sinaiticus",
            reading="Only begotten",
            note="Multiple sentences! Additional manuscript context beyond the opener.",
            source="Codex 01",
        ),
        _make_variant(
            entry_id="v2",
            witness="Codex Vaticanus",
            reading="Begotten",
            note="Secondary note.",
            source="Codex 03",
        ),
    ]

    overview = build_reliability_overview(
        osis="John.3.16",
        notes=[supportive_note, critical_note, supportive_extra, neutral_note, empty_note],
        variants=variants,
        note_limit=2,
        manuscript_limit=1,
    )

    assert overview.mode == "apologetic"
    assert [bullet.summary for bullet in overview.consensus] == [
        "Supportive note title.",
        "Second supportive point explained with more detail.",
    ]
    assert overview.consensus[0].citations == (
        "Smith 2020",
        "Archive A",
        "Extra Source",
    )
    assert [bullet.summary for bullet in overview.disputed] == [
        "Critical claim.",
    ]
    assert [bullet.summary for bullet in overview.manuscripts] == [
        "Codex Sinaiticus notes this verse. It reads \"Only begotten\". Multiple sentences.",
    ]

    skeptical_overview = build_reliability_overview(
        osis="John.3.16",
        notes=[supportive_note, critical_note, supportive_extra, neutral_note, empty_note],
        variants=variants,
        mode="skeptical",
        note_limit=2,
        manuscript_limit=1,
    )

    assert skeptical_overview.mode == "skeptical"
    assert [bullet.summary for bullet in skeptical_overview.consensus] == [
        "Critical claim.",
        "Neutral perspective outlining context.",
    ]
    assert [bullet.summary for bullet in skeptical_overview.disputed] == [
        "Supportive note title.",
        "Second supportive point explained with more detail.",
    ]


def test_note_helpers_produce_concise_summary_and_deduplicate_citations():
    long_text = (
        "This sentence is intentionally lengthy to test the truncation logic "
        "that should still return a clean summary even when there are more "
        "than one hundred and eighty characters in the content provided to the helper.\n"
        "Another sentence follows but should be ignored."
    )
    summary = _first_sentence(long_text)
    assert summary.endswith(".")
    assert "\n" not in summary
    assert len(summary) <= 181

    evidences = (
        _make_evidence(evidence_id="e1", citation="Ref A", source_ref="Ref A"),
        _make_evidence(evidence_id="e2", citation="Ref B", source_ref=""),
        _make_evidence(evidence_id="e3", citation="", source_ref="Ref C"),
        _make_evidence(evidence_id="e4", citation="Ref D", source_ref="Ref C"),
    )
    note = _make_note(
        note_id="long",
        stance="supportive",
        title=None,
        body=long_text,
        evidences=evidences,
    )

    bullet = _note_to_bullet(note)
    assert bullet is not None
    assert bullet.summary == summary
    assert bullet.citations == ("Ref A", "Ref B", "Ref C")

    blank_note = _make_note(
        note_id="blank",
        stance=None,
        title=None,
        body="   ",
    )
    assert _note_to_bullet(blank_note) is None
    assert _extract_citations(note) == ["Ref A", "Ref B", "Ref C"]


def test_manuscript_helpers_respect_limits_and_fallbacks():
    primary_entry = _make_variant(
        entry_id="v1",
        witness="Papyrus 66",
        reading="God so loved",
        note="Detailed observation! Additional nuance after the first sentence.",
        source="P66",
    )
    fallback_entry = _make_variant(
        entry_id="v2",
        witness=None,
        reading="",
        note=None,
        source=None,
    )

    bullets = _manuscript_bullets([primary_entry, fallback_entry], limit=1)
    assert len(bullets) == 1
    bullet = bullets[0]
    assert bullet.summary == (
        'Papyrus 66 notes this verse. It reads "God so loved". Detailed observation.'
    )
    assert bullet.citations == ("P66", "Papyrus 66")

    assert _summarize_manuscript(fallback_entry) == "A manuscript notes this verse."
