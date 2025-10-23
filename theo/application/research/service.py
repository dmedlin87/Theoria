"""Application service orchestrating research workflows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

from theo.domain import (
    CrossReferenceEntry,
    DssLinkEntry,
    FallacyHit,
    HistoricityEntry,
    Hypothesis,
    HypothesisDraft,
    MorphToken,
    ReliabilityOverview,
    ResearchNote,
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
    VariantEntry,
    Verse,
    build_reliability_overview,
    fallacy_detect,
    fetch_cross_references,
    fetch_dss_links,
    fetch_morphology,
    fetch_passage,
    historicity_search,
    variants_apparatus,
)
from theo.domain.repositories import HypothesisRepository, ResearchNoteRepository
from theo.domain.research.datasets import report_templates_dataset


@dataclass(frozen=True, slots=True)
class ReportSection:
    title: str
    summary: str | None
    items: list[dict[str, object]]


@dataclass(frozen=True, slots=True)
class ResearchReport:
    osis: str
    stance: str
    summary: str
    sections: list[ReportSection]
    meta: dict[str, object]


class ResearchService:
    """Facade aggregating research-focused application logic."""

    def __init__(
        self,
        notes_repository: ResearchNoteRepository,
        *,
        hypothesis_repository: HypothesisRepository | None = None,
        fetch_dss_links_func: Callable[[str], list[DssLinkEntry]] = fetch_dss_links,
    ):
        self._notes_repository = notes_repository
        self._hypothesis_repository = hypothesis_repository
        self._fetch_dss_links = fetch_dss_links_func

    # Dataset backed lookups -------------------------------------------------

    def fetch_passage(self, osis: str, translation: str | None = None) -> list[Verse]:
        return fetch_passage(osis, translation)

    def fetch_cross_references(self, osis: str, *, limit: int = 25) -> list[CrossReferenceEntry]:
        return fetch_cross_references(osis, limit=limit)

    def variants_apparatus(
        self,
        osis: str,
        *,
        categories: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[VariantEntry]:
        return variants_apparatus(osis, categories=categories, limit=limit)

    def fetch_dss_links(self, osis: str) -> list[DssLinkEntry]:
        return self._fetch_dss_links(osis)

    def fetch_morphology(self, osis: str) -> list[MorphToken]:
        return fetch_morphology(osis)

    def historicity_search(
        self,
        query: str,
        *,
        year_from: int | None = None,
        year_to: int | None = None,
        limit: int = 20,
    ) -> list[HistoricityEntry]:
        return historicity_search(
            query,
            year_from=year_from,
            year_to=year_to,
            limit=limit,
        )

    def fallacy_detect(
        self,
        text: str,
        *,
        min_confidence: float = 0.0,
    ) -> list[FallacyHit]:
        return fallacy_detect(text, min_confidence=min_confidence)

    # Hypotheses -------------------------------------------------------------

    def list_hypotheses(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
        min_confidence: float | None = None,
        query: str | None = None,
    ) -> list[Hypothesis]:
        if not self._hypothesis_repository:
            return []
        return self._hypothesis_repository.list(
            statuses=statuses,
            min_confidence=min_confidence,
            query=query,
        )

    def create_hypothesis(self, draft: HypothesisDraft) -> Hypothesis:
        if not self._hypothesis_repository:
            raise RuntimeError("Hypothesis repository is not configured")
        return self._hypothesis_repository.create(draft)

    def update_hypothesis(
        self, hypothesis_id: str, changes: Mapping[str, object]
    ) -> Hypothesis:
        if not self._hypothesis_repository:
            raise RuntimeError("Hypothesis repository is not configured")
        return self._hypothesis_repository.update(hypothesis_id, changes)

    # Research notes ---------------------------------------------------------

    def list_notes(
        self,
        osis: str,
        *,
        stance: str | None = None,
        claim_type: str | None = None,
        tag: str | None = None,
        min_confidence: float | None = None,
    ) -> list[ResearchNote]:
        return self._notes_repository.list_for_osis(
            osis,
            stance=stance,
            claim_type=claim_type,
            tag=tag,
            min_confidence=min_confidence,
        )

    def create_note(
        self,
        draft: ResearchNoteDraft,
        *,
        commit: bool = True,
    ) -> ResearchNote:
        return self._notes_repository.create(draft, commit=commit)

    def preview_note(self, draft: ResearchNoteDraft) -> ResearchNote:
        return self._notes_repository.preview(draft)

    def update_note(
        self,
        note_id: str,
        changes: Mapping[str, object],
        *,
        evidences: Sequence[ResearchNoteEvidenceDraft] | None = None,
    ) -> ResearchNote:
        return self._notes_repository.update(
            note_id,
            changes,
            evidences=evidences,
        )

    def delete_note(self, note_id: str) -> None:
        self._notes_repository.delete(note_id)

    # Higher level composites ------------------------------------------------

    def build_reliability_overview(
        self,
        osis: str,
        *,
        mode: str | None = None,
        note_limit: int = 3,
        manuscript_limit: int = 3,
    ) -> ReliabilityOverview:
        notes = self.list_notes(osis)
        manuscripts = self.variants_apparatus(
            osis,
            categories=["manuscript"],
            limit=manuscript_limit,
        )
        return build_reliability_overview(
            osis=osis,
            notes=notes,
            variants=manuscripts,
            mode=mode,
            note_limit=note_limit,
            manuscript_limit=manuscript_limit,
        )

    def report_build(
        self,
        osis: str,
        *,
        stance: str,
        claims: Iterable[Mapping[str, object]] | None = None,
        historicity_query: str | None = None,
        narrative_text: str | None = None,
        include_fallacies: bool = False,
        variants_limit: int | None = None,
        citations_limit: int = 5,
        min_fallacy_confidence: float = 0.0,
    ) -> ResearchReport:
        templates = report_templates_dataset()
        stance_key = stance.lower()
        stance_key = {"skeptical": "critical"}.get(stance_key, stance_key)
        template = templates.get(stance_key) or templates.get("default", {})
        summary_template = str(
            template.get("summary", "Research briefing for {osis} ({stance}).")
        )
        section_names = template.get("sections", {})

        variant_entries = self.variants_apparatus(osis, limit=variants_limit)
        variants_section = ReportSection(
            title=section_names.get("variants", "Textual Variants"),
            summary="Key apparatus notes for the passage.",
            items=[
                {
                    "id": entry.id,
                    "osis": entry.osis,
                    "category": entry.category,
                    "reading": entry.reading,
                    "note": entry.note,
                    "source": entry.source,
                    "witness": entry.witness,
                    "translation": entry.translation,
                    "confidence": entry.confidence,
                }
                for entry in variant_entries
            ],
        )

        query = historicity_query or osis
        citation_entries: list[HistoricityEntry] = []
        if query:
            citation_entries = self.historicity_search(query, limit=citations_limit)
        citations_section = ReportSection(
            title=section_names.get("historicity", "Historicity Sources"),
            summary="Citations touching on people, places, or claims in the passage.",
            items=[
                {
                    "id": entry.id,
                    "title": entry.title,
                    "authors": entry.authors,
                    "year": entry.year,
                    "summary": entry.summary,
                    "source": entry.source,
                    "url": entry.url,
                    "tags": entry.tags,
                    "score": entry.score,
                }
                for entry in citation_entries
            ],
        )

        fallacy_hits: list[FallacyHit] = []
        if include_fallacies and narrative_text:
            fallacy_hits = self.fallacy_detect(
                narrative_text,
                min_confidence=min_fallacy_confidence,
            )
        fallacy_section = ReportSection(
            title=section_names.get("fallacies", "Fallacy Audit"),
            summary=(
                "Potential rhetorical weaknesses detected in the provided argument"
                if include_fallacies and narrative_text
                else "No fallacy audit requested."
            ),
            items=[
                {
                    "id": hit.id,
                    "name": hit.name,
                    "category": hit.category,
                    "description": hit.description,
                    "severity": hit.severity,
                    "confidence": hit.confidence,
                    "matches": hit.matches,
                }
                for hit in fallacy_hits
            ],
        )

        claims_section = ReportSection(
            title=section_names.get("claims", "Key Claims"),
            summary="Claims or thesis statements supplied by the caller.",
            items=[dict(claim) for claim in (claims or [])],
        )

        sections = [variants_section, citations_section]
        if include_fallacies:
            sections.append(fallacy_section)
        sections.append(claims_section)

        meta = {
            "variant_count": len(variants_section.items),
            "citation_count": len(citations_section.items),
            "fallacy_count": len(fallacy_section.items) if include_fallacies else 0,
        }

        summary = summary_template.format(osis=osis, stance=stance)
        return ResearchReport(
            osis=osis,
            stance=stance,
            summary=summary,
            sections=sections,
            meta=meta,
        )


__all__ = [
    "ReportSection",
    "ResearchReport",
    "ResearchService",
]
