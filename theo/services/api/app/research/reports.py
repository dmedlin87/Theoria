"""Research report synthesis utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .datasets import report_templates_dataset
from .fallacies import fallacy_detect, FallacyHit
from .historicity import historicity_search, HistoricityEntry
from .variants import variants_apparatus


@dataclass(slots=True)
class ReportSection:
    title: str
    summary: str | None
    items: list[dict[str, object]]


@dataclass(slots=True)
class ResearchReport:
    osis: str
    stance: str
    summary: str
    sections: list[ReportSection]
    meta: dict[str, object]


def _resolve_template(stance: str) -> dict[str, object]:
    templates = report_templates_dataset()
    key = stance.lower()
    return templates.get(key) or templates.get("default", {})


def report_build(
    osis: str,
    *,
    stance: str,
    claims: Iterable[dict[str, object]] | None = None,
    historicity_query: str | None = None,
    narrative_text: str | None = None,
    include_fallacies: bool = False,
    variants_limit: int | None = None,
    citations_limit: int = 5,
    min_fallacy_confidence: float = 0.0,
) -> ResearchReport:
    """Compile a research report combining textual, historical, and rhetorical data."""

    template = _resolve_template(stance)
    summary_template = template.get("summary", "Research briefing for {osis} ({stance}).")
    section_names = template.get("sections", {})

    variant_entries = variants_apparatus(osis, limit=variants_limit)
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
        citation_entries = historicity_search(query, limit=citations_limit)
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
        fallacy_hits = fallacy_detect(
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
