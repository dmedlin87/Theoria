"""Reader + research dock endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.settings import get_settings
from ..models.research import (
    ContradictionSearchResponse,
    CrossReferenceResponse,
    DeadSeaScrollsResponse,
    FallacyDetectRequest,
    FallacyDetectResponse,
    GeoPlaceSearchResponse,
    HistoricitySearchResponse,
    MorphologyResponse,
    ReportBuildRequest,
    ResearchReportResponse,
    ResearchNoteCreate,
    ResearchNoteResponse,
    ResearchNotesResponse,
    ResearchNoteUpdate,
    ScriptureResponse,
    VariantApparatusResponse,
)
from ..research import (
    create_research_note,
    delete_research_note,
    fallacy_detect,
    fetch_cross_references,
    fetch_dead_sea_scroll_links,
    fetch_morphology,
    fetch_passage,
    historicity_search,
    get_notes_for_osis,
    report_build,
    update_research_note,
    lookup_geo_places,
    search_contradictions,
    variants_apparatus,
)

router = APIRouter()


@router.get("/scripture", response_model=ScriptureResponse)
def get_scripture(
    osis: str = Query(..., description="OSIS reference or range"),
    translation: str | None = Query(
        default="SBLGNT", description="Preferred translation code"
    ),
) -> ScriptureResponse:
    verses = fetch_passage(osis, translation)
    translation_code = verses[0].translation if verses else (translation or "SBLGNT")
    return ScriptureResponse(
        osis=osis,
        translation=translation_code,
        verses=[
            {
                "osis": verse.osis,
                "translation": verse.translation,
                "text": verse.text,
                "book": verse.book,
                "chapter": verse.chapter,
                "verse": verse.verse,
            }
            for verse in verses
        ],
        meta={"count": len(verses)},
    )


@router.get("/crossrefs", response_model=CrossReferenceResponse)
def get_crossrefs(
    osis: str = Query(..., description="Verse to fetch cross-references for"),
    limit: int = Query(default=25, ge=1, le=100),
) -> CrossReferenceResponse:
    results = fetch_cross_references(osis, limit=limit)
    return CrossReferenceResponse(
        osis=osis,
        results=[
            {
                "source": item.source,
                "target": item.target,
                "weight": item.weight,
                "relation_type": item.relation_type,
                "summary": item.summary,
                "dataset": item.dataset,
            }
            for item in results
        ],
        total=len(results),
    )


@router.get("/dss", response_model=DeadSeaScrollsResponse)
def get_dead_sea_scroll_links(
    osis: str = Query(..., description="Verse to fetch Dead Sea Scrolls links for"),
) -> DeadSeaScrollsResponse:
    links = fetch_dead_sea_scroll_links(osis)
    return DeadSeaScrollsResponse(
        osis=osis,
        links=[
            {
                "id": link.id,
                "fragment": link.fragment,
                "scroll": link.scroll,
                "summary": link.summary,
                "source": link.source,
                "url": link.url,
            }
            for link in links
        ],
        total=len(links),
    )


@router.get("/variants", response_model=VariantApparatusResponse)
def get_variants(
    osis: str = Query(..., description="Verse or range to retrieve apparatus notes for"),
    category: list[str] | None = Query(
        default=None,
        description="Optional category filters such as manuscript, translation, version",
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=50,
        description="Maximum number of apparatus entries to return",
    ),
) -> VariantApparatusResponse:
    categories = category or None
    entries = variants_apparatus(osis, categories=categories, limit=limit)
    return VariantApparatusResponse(
        osis=osis,
        readings=[
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
            for entry in entries
        ],
        total=len(entries),
    )


@router.get("/morphology", response_model=MorphologyResponse)
def get_morphology(
    osis: str = Query(..., description="Verse to fetch morphology for"),
) -> MorphologyResponse:
    tokens = fetch_morphology(osis)
    return MorphologyResponse(
        osis=osis,
        tokens=[
            {
                "osis": token.osis,
                "surface": token.surface,
                "lemma": token.lemma,
                "morph": token.morph,
                "gloss": token.gloss,
                "position": token.position,
            }
            for token in tokens
        ],
    )


@router.get("/notes", response_model=ResearchNotesResponse)
def list_notes(
    osis: str = Query(..., description="Anchor OSIS reference"),
    stance: str | None = Query(
        default=None,
        description="Optional stance label to filter by",
    ),
    claim_type: str | None = Query(
        default=None,
        description="Optional claim type to filter by",
    ),
    tag: str | None = Query(
        default=None,
        description="Filter notes containing a specific tag",
    ),
    min_confidence: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score inclusive",
    ),
    session: Session = Depends(get_session),
) -> ResearchNotesResponse:
    notes = get_notes_for_osis(
        session,
        osis,
        stance=stance,
        claim_type=claim_type,
        tag=tag,
        min_confidence=min_confidence,
    )
    return ResearchNotesResponse(
        osis=osis,
        notes=notes,
        total=len(notes),
    )


@router.get("/historicity", response_model=HistoricitySearchResponse)
def get_historicity(
    query: str = Query(..., min_length=2, description="Keywords to locate related citations"),
    year_from: int | None = Query(
        default=None, description="Minimum publication year inclusive"
    ),
    year_to: int | None = Query(
        default=None, description="Maximum publication year inclusive"
    ),
    limit: int = Query(default=20, ge=1, le=50),
) -> HistoricitySearchResponse:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise HTTPException(status_code=422, detail="year_from cannot exceed year_to")

    results = historicity_search(
        query,
        year_from=year_from,
        year_to=year_to,
        limit=limit,
    )
    return HistoricitySearchResponse(
        query=query,
        results=[
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
            for entry in results
        ],
        total=len(results),
    )


@router.post("/notes", response_model=ResearchNoteResponse, status_code=201)
def create_note(
    payload: ResearchNoteCreate,
    session: Session = Depends(get_session),
) -> ResearchNoteResponse:
    if not payload.body.strip():
        raise HTTPException(status_code=422, detail="Note body cannot be empty")

    note = create_research_note(
        session,
        osis=payload.osis,
        title=payload.title,
        body=payload.body,
        stance=payload.stance,
        claim_type=payload.claim_type,
        confidence=payload.confidence,
        tags=payload.tags,
        evidences=[e.model_dump() for e in payload.evidences or []],
    )
    return ResearchNoteResponse(note=note)


@router.patch("/notes/{note_id}", response_model=ResearchNoteResponse)
def patch_note(
    note_id: str,
    payload: ResearchNoteUpdate,
    session: Session = Depends(get_session),
) -> ResearchNoteResponse:
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=422, detail="No fields provided for update")

    if "body" in update_data and update_data["body"] is not None:
        if not update_data["body"].strip():
            raise HTTPException(status_code=422, detail="Note body cannot be empty")

    evidence_payload = None
    if "evidences" in update_data:
        raw_evidences = payload.evidences
        evidence_payload = [] if raw_evidences is None else [
            evidence.model_dump() for evidence in raw_evidences
        ]
        update_data.pop("evidences", None)

    note = update_research_note(
        session,
        note_id,
        changes=update_data,
        evidences=evidence_payload,
    )
    return ResearchNoteResponse(note=note)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(
    note_id: str,
    session: Session = Depends(get_session),
) -> Response:
    delete_research_note(session, note_id)
    return Response(status_code=204)


@router.post("/fallacies", response_model=FallacyDetectResponse)
def detect_fallacies(payload: FallacyDetectRequest) -> FallacyDetectResponse:
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="Text must not be empty")

    detections = fallacy_detect(
        payload.text,
        min_confidence=payload.min_confidence,
    )
    return FallacyDetectResponse(
        text=payload.text,
        detections=[
            {
                "id": hit.id,
                "name": hit.name,
                "category": hit.category,
                "description": hit.description,
                "severity": hit.severity,
                "confidence": hit.confidence,
                "matches": hit.matches,
            }
            for hit in detections
        ],
        total=len(detections),
    )


@router.post("/report", response_model=ResearchReportResponse)
def build_report(payload: ReportBuildRequest) -> ResearchReportResponse:
    if payload.include_fallacies and not payload.narrative_text:
        raise HTTPException(
            status_code=422,
            detail="narrative_text is required when include_fallacies is true",
        )

    report = report_build(
        payload.osis,
        stance=payload.stance,
        claims=[claim.model_dump() for claim in payload.claims or []],
        historicity_query=payload.historicity_query,
        narrative_text=payload.narrative_text,
        include_fallacies=payload.include_fallacies,
        variants_limit=payload.variants_limit,
        citations_limit=payload.citations_limit,
        min_fallacy_confidence=payload.min_fallacy_confidence,
    )
    return ResearchReportResponse(
        report={
            "osis": report.osis,
            "stance": report.stance,
            "summary": report.summary,
            "sections": [
                {
                    "title": section.title,
                    "summary": section.summary,
                    "items": section.items,
                }
                for section in report.sections
            ],
            "meta": report.meta,
        }
    )


@router.get("/contradictions", response_model=ContradictionSearchResponse)
def list_contradictions(
    osis: list[str] = Query(..., description="OSIS reference or list of references"),
    topic: str | None = Query(default=None, description="Optional topic tag filter"),
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ContradictionSearchResponse:
    settings = get_settings()
    if not getattr(settings, "contradictions_enabled", True):
        return ContradictionSearchResponse(items=[])

    items = search_contradictions(session, osis=osis, topic=topic, limit=limit)
    return ContradictionSearchResponse(items=items)


@router.get("/geo/search", response_model=GeoPlaceSearchResponse)
def lookup_geo(
    query: str = Query(..., description="Place name or alias"),
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> GeoPlaceSearchResponse:
    settings = get_settings()
    if not getattr(settings, "geo_enabled", True):
        return GeoPlaceSearchResponse(items=[])

    items = lookup_geo_places(session, query=query, limit=limit)
    return GeoPlaceSearchResponse(items=items)
