import pytest

from theo.application.research import service as service_module
from theo.application.research.service import ResearchService
from theo.domain import (
    Hypothesis,
    HypothesisDraft,
    ResearchNote,
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
    VariantEntry,
)


class _RecordingNotesRepository:
    """Repository stub capturing calls made by ``ResearchService``."""

    def __init__(self) -> None:
        self.list_calls: list[tuple[str, dict[str, object]]] = []
        self.create_calls: list[tuple[ResearchNoteDraft, bool]] = []
        self.preview_calls: list[ResearchNoteDraft] = []
        self.update_calls: list[tuple[str, dict[str, object], tuple[ResearchNoteEvidenceDraft, ...] | None]] = []
        self.delete_calls: list[str] = []
        self.list_return: list[ResearchNote] = []
        self.create_return: ResearchNote | None = None
        self.preview_return: ResearchNote | None = None
        self.update_return: ResearchNote | None = None

    def list_for_osis(self, osis: str, **filters: object) -> list[ResearchNote]:
        self.list_calls.append((osis, dict(filters)))
        return list(self.list_return)

    def create(self, draft: ResearchNoteDraft, *, commit: bool = True) -> ResearchNote:
        assert self.create_return is not None, "create_return must be set by the test"
        self.create_calls.append((draft, commit))
        return self.create_return

    def preview(self, draft: ResearchNoteDraft) -> ResearchNote:
        assert self.preview_return is not None, "preview_return must be set by the test"
        self.preview_calls.append(draft)
        return self.preview_return

    def update(
        self,
        note_id: str,
        changes: dict[str, object],
        *,
        evidences: tuple[ResearchNoteEvidenceDraft, ...] | None = None,
    ) -> ResearchNote:
        assert self.update_return is not None, "update_return must be set by the test"
        normalized_evidences = tuple(evidences) if evidences is not None else None
        self.update_calls.append((note_id, dict(changes), normalized_evidences))
        return self.update_return

    def delete(self, note_id: str) -> None:  # pragma: no cover - behaviour verified by calls list
        self.delete_calls.append(note_id)


class _RecordingHypothesisRepository:
    """Repository stub capturing hypothesis interactions."""

    def __init__(self) -> None:
        self.list_calls: list[dict[str, object]] = []
        self.create_calls: list[HypothesisDraft] = []
        self.update_calls: list[tuple[str, dict[str, object]]] = []
        self.list_return: list[Hypothesis] = []
        self.create_return: Hypothesis | None = None
        self.update_return: Hypothesis | None = None

    def list(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
        min_confidence: float | None = None,
        query: str | None = None,
    ) -> list[Hypothesis]:
        filters = {
            "statuses": statuses,
            "min_confidence": min_confidence,
            "query": query,
        }
        self.list_calls.append(filters)
        return list(self.list_return)

    def create(self, draft: HypothesisDraft) -> Hypothesis:
        assert self.create_return is not None, "create_return must be set by the test"
        self.create_calls.append(draft)
        return self.create_return

    def update(self, hypothesis_id: str, changes: dict[str, object]) -> Hypothesis:
        assert self.update_return is not None, "update_return must be set by the test"
        self.update_calls.append((hypothesis_id, dict(changes)))
        return self.update_return


@pytest.fixture
def notes_repository() -> _RecordingNotesRepository:
    return _RecordingNotesRepository()


def _sample_note(note_id: str = "note-1") -> ResearchNote:
    return ResearchNote(
        id=note_id,
        osis="John.3.16",
        body="For God so loved the world.",
        title="Famous verse",
        stance="affirming",
        claim_type="theology",
        confidence=0.9,
    )


def _sample_hypothesis(hypothesis_id: str = "hypo-1") -> Hypothesis:
    return Hypothesis(
        id=hypothesis_id,
        claim="Claim text",
        confidence=0.5,
        status="active",
    )


def test_list_hypotheses_returns_empty_without_repository(notes_repository: _RecordingNotesRepository) -> None:
    service = ResearchService(notes_repository)

    assert service.list_hypotheses() == []


def test_create_hypothesis_requires_repository(notes_repository: _RecordingNotesRepository) -> None:
    service = ResearchService(notes_repository)
    draft = HypothesisDraft(claim="Claim", confidence=0.6, status="active")

    with pytest.raises(RuntimeError, match="repository is not configured"):
        service.create_hypothesis(draft)


def test_update_hypothesis_requires_repository(notes_repository: _RecordingNotesRepository) -> None:
    service = ResearchService(notes_repository)

    with pytest.raises(RuntimeError, match="repository is not configured"):
        service.update_hypothesis("hypo-1", {"status": "confirmed"})


def test_hypothesis_operations_delegate_to_repository(notes_repository: _RecordingNotesRepository) -> None:
    hypothesis_repository = _RecordingHypothesisRepository()
    hypothesis_repository.list_return = [_sample_hypothesis()]
    hypothesis_repository.create_return = _sample_hypothesis("hypo-created")
    hypothesis_repository.update_return = _sample_hypothesis("hypo-updated")

    service = ResearchService(
        notes_repository,
        hypothesis_repository=hypothesis_repository,
    )

    listed = service.list_hypotheses(
        statuses=("active",),
        min_confidence=0.75,
        query="paul",
    )
    assert listed == hypothesis_repository.list_return
    assert hypothesis_repository.list_calls == [
        {"statuses": ("active",), "min_confidence": 0.75, "query": "paul"}
    ]

    draft = HypothesisDraft(claim="Another claim", confidence=0.7, status="active")
    created = service.create_hypothesis(draft)
    assert created == hypothesis_repository.create_return
    assert hypothesis_repository.create_calls == [draft]

    updated = service.update_hypothesis("hypo-1", {"status": "confirmed"})
    assert updated == hypothesis_repository.update_return
    assert hypothesis_repository.update_calls == [("hypo-1", {"status": "confirmed"})]


def test_list_notes_delegates_to_repository(notes_repository: _RecordingNotesRepository) -> None:
    service = ResearchService(notes_repository)
    notes_repository.list_return = [_sample_note()]

    result = service.list_notes(
        "John.3.16",
        stance="skeptical",
        claim_type="historicity",
        tag="prophecy",
        min_confidence=0.4,
    )

    assert result == notes_repository.list_return
    assert notes_repository.list_calls == [
        (
            "John.3.16",
            {
                "stance": "skeptical",
                "claim_type": "historicity",
                "tag": "prophecy",
                "min_confidence": 0.4,
            },
        )
    ]


def test_note_mutations_delegate_to_repository(notes_repository: _RecordingNotesRepository) -> None:
    service = ResearchService(notes_repository)
    draft = ResearchNoteDraft(osis="John.3.16", body="Some commentary")
    notes_repository.create_return = _sample_note("note-created")
    created = service.create_note(draft, commit=False)
    assert created == notes_repository.create_return
    assert notes_repository.create_calls == [(draft, False)]

    notes_repository.preview_return = _sample_note("note-preview")
    previewed = service.preview_note(draft)
    assert previewed == notes_repository.preview_return
    assert notes_repository.preview_calls == [draft]

    evidence = ResearchNoteEvidenceDraft(citation="John 3:16", snippet="Snippet")
    notes_repository.update_return = _sample_note("note-updated")
    updated = service.update_note(
        "note-1",
        {"confidence": 0.95},
        evidences=[evidence],
    )
    assert updated == notes_repository.update_return
    assert notes_repository.update_calls == [
        ("note-1", {"confidence": 0.95}, (evidence,))
    ]

    service.delete_note("note-2")
    assert notes_repository.delete_calls == ["note-2"]


def test_build_reliability_overview_passes_options(
    monkeypatch: pytest.MonkeyPatch,
    notes_repository: _RecordingNotesRepository,
) -> None:
    service = ResearchService(notes_repository)
    notes_repository.list_return = [_sample_note()]
    variant_entry = VariantEntry(
        id="var-1",
        osis="John.3.16",
        category="manuscript",
        reading="Reading",
    )

    captured: dict[str, object] = {}

    def fake_variants(
        osis: str,
        *,
        categories: list[str] | None = None,
        limit: int | None = None,
    ) -> list[VariantEntry]:
        captured["variants_call"] = (osis, categories, limit)
        return [variant_entry]

    def fake_build(**kwargs: object) -> str:
        captured["build_kwargs"] = kwargs
        return "overview"

    monkeypatch.setattr(service_module, "variants_apparatus", fake_variants)
    monkeypatch.setattr(service_module, "build_reliability_overview", fake_build)

    overview = service.build_reliability_overview(
        "John.3.16",
        mode="skeptical",
        note_limit=1,
        manuscript_limit=2,
    )

    assert overview == "overview"
    assert captured["variants_call"] == (
        "John.3.16",
        ["manuscript"],
        2,
    )
    assert captured["build_kwargs"] == {
        "osis": "John.3.16",
        "notes": notes_repository.list_return,
        "variants": [variant_entry],
        "mode": "skeptical",
        "note_limit": 1,
        "manuscript_limit": 2,
    }
    assert notes_repository.list_calls == [
        (
            "John.3.16",
            {
                "stance": None,
                "claim_type": None,
                "tag": None,
                "min_confidence": None,
            },
        )
    ]


def test_fetch_dss_links_uses_injected_function(notes_repository: _RecordingNotesRepository) -> None:
    captured: list[str] = []

    def fake_fetch(osis: str) -> list[str]:
        captured.append(osis)
        return ["link"]

    service = ResearchService(
        notes_repository,
        fetch_dss_links_func=fake_fetch,
    )

    result = service.fetch_dss_links("John.3.16")

    assert result == ["link"]
    assert captured == ["John.3.16"]
