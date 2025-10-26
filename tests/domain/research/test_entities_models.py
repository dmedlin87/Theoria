"""Unit tests for :mod:`theo.domain.research.entities`."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from theo.domain.research.entities import (
    Hypothesis,
    HypothesisDraft,
    HypothesisNotFoundError,
    ResearchNote,
    ResearchNoteDraft,
    ResearchNoteEvidence,
    ResearchNoteEvidenceDraft,
    ResearchNoteNotFoundError,
)


def test_research_note_immutability_and_relationships() -> None:
    evidence = ResearchNoteEvidence(
        id="e1",
        source_type="book",
        source_ref="ISBN123",
        osis_refs=("Gen.1.1",),
        citation="Author, Theology (2023)",
        snippet="In the beginning...",
        meta={"page": 10},
    )
    note = ResearchNote(
        id="n1",
        osis="Gen.1.1",
        body="God created the heavens and the earth.",
        title="Creation",
        stance="affirm",
        claim_type="theology",
        confidence=0.8,
        tags=("creation", "genesis"),
        evidences=(evidence,),
        request_id="req-1",
        created_by="user-1",
        tenant_id="tenant-1",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    assert note.evidences == (evidence,)
    assert note.tags == ("creation", "genesis")
    assert note == ResearchNote(
        id="n1",
        osis="Gen.1.1",
        body="God created the heavens and the earth.",
        title="Creation",
        stance="affirm",
        claim_type="theology",
        confidence=0.8,
        tags=("creation", "genesis"),
        evidences=(evidence,),
        request_id="req-1",
        created_by="user-1",
        tenant_id="tenant-1",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    with pytest.raises(FrozenInstanceError):
        note.body = "Changed"  # type: ignore[misc]


def test_research_note_draft_defaults_to_empty_evidence() -> None:
    draft = ResearchNoteDraft(osis="Gen.1.1", body="Summary")

    assert draft.evidences == ()
    assert draft.tags is None

    evidence_draft = ResearchNoteEvidenceDraft(source_type="article")
    draft_with_evidence = ResearchNoteDraft(
        osis="Gen.1.1",
        body="Summary",
        evidences=(evidence_draft,),
    )

    assert draft_with_evidence.evidences == (evidence_draft,)


def test_hypothesis_value_object_behaviour() -> None:
    hypothesis = Hypothesis(
        id="h1",
        claim="The passage supports doctrine X",
        confidence=0.7,
        status="draft",
        trail_id="trail-1",
        supporting_passage_ids=("p1", "p2"),
        contradicting_passage_ids=("p3",),
        perspective_scores={"tradition": 0.8},
        metadata={"reviewed": False},
    )

    duplicate = Hypothesis(
        id="h1",
        claim="The passage supports doctrine X",
        confidence=0.7,
        status="draft",
        trail_id="trail-1",
        supporting_passage_ids=("p1", "p2"),
        contradicting_passage_ids=("p3",),
        perspective_scores={"tradition": 0.8},
        metadata={"reviewed": False},
    )

    assert hypothesis == duplicate
    with pytest.raises(FrozenInstanceError):
        hypothesis.status = "final"  # type: ignore[misc]


def test_hypothesis_draft_defaults() -> None:
    draft = HypothesisDraft(claim="Claim", confidence=0.5, status="pending")

    assert draft.supporting_passage_ids is None
    assert draft.metadata is None


def test_research_errors_inherit_key_error() -> None:
    assert issubclass(ResearchNoteNotFoundError, KeyError)
    assert issubclass(HypothesisNotFoundError, KeyError)
