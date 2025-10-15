"""Reader + research dock endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session
from theo.application.facades.research import (
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
    ResearchService,
    get_research_service,
)
from theo.domain.research import ResearchNoteNotFoundError
from theo.application.facades.settings import get_settings
from ..models.research import (
    CommentarySearchResponse,
    ContradictionSearchResponse,
    CrossReference,
    CrossReferenceResponse,
    DssLink,
    DssLinksResponse,
    FallacyDetectRequest,
    FallacyDetectResponse,
    FallacyDetection,
    GeoPlaceSearchResponse,
    GeoVerseResponse,
    HistoricityEntry,
    HistoricitySearchResponse,
    MorphToken,
    MorphologyResponse,
    OverviewBullet,
    ReliabilityOverviewResponse,
    ReportBuildRequest,
    ResearchNote,
    ResearchNoteCreate,
    ResearchNoteResponse,
    ResearchNotesResponse,
    ResearchNoteUpdate,
    ResearchReport,
    ResearchReportResponse,
    ScriptureResponse,
    ScriptureVerse,
    VariantApparatusResponse,
    VariantReading,
)
from ..research import (
    lookup_geo_places,
    places_for_osis,
    search_commentaries,
    search_contradictions,
)

router = APIRouter()


def _research_service(session: Session = Depends(get_session)) -> ResearchService:
    return get_research_service(session)

def _to_evidence_drafts(
    evidences: list[NoteEvidenceCreate] | None,
) -> tuple[ResearchNoteEvidenceDraft, ...]:
    if not evidences:
        return ()
    return tuple(
        ResearchNoteEvidenceDraft(
            source_type=evidence.source_type,
            source_ref=evidence.source_ref,
            osis_refs=tuple(evidence.osis_refs or []) or None,
            citation=evidence.citation,
            snippet=evidence.snippet,
            meta=evidence.meta,
        )
        for evidence in evidences
    )


@router.get("/scripture", response_model=ScriptureResponse)
def get_scripture(
    osis: str = Query(..., description="OSIS reference or range"),
    translation: str | None = Query(
        default="SBLGNT", description="Preferred translation code"
    ),
    service: ResearchService = Depends(_research_service),
) -> ScriptureResponse:
    verses = service.fetch_passage(osis, translation)
    translation_code = verses[0].translation if verses else (translation or "SBLGNT")
    return ScriptureResponse(
        osis=osis,
        translation=translation_code,
        verses=[ScriptureVerse.model_validate(verse) for verse in verses],
        meta={"count": len(verses)},
    )


@router.get("/crossrefs", response_model=CrossReferenceResponse)
def get_crossrefs(
    osis: str = Query(..., description="Verse to fetch cross-references for"),
    limit: int = Query(default=25, ge=1, le=100),
    service: ResearchService = Depends(_research_service),
) -> CrossReferenceResponse:
    results = service.fetch_cross_references(osis, limit=limit)
    return CrossReferenceResponse(
        osis=osis,
        results=[CrossReference.model_validate(item) for item in results],
        total=len(results),
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
    service: ResearchService = Depends(_research_service),
) -> VariantApparatusResponse:
    categories = category or None
    entries = service.variants_apparatus(osis, categories=categories, limit=limit)
    return VariantApparatusResponse(
        osis=osis,
        readings=[VariantReading.model_validate(entry) for entry in entries],
        total=len(entries),
    )


@router.get("/dss-links", response_model=DssLinksResponse)
def get_dss_links(
    osis: str = Query(..., description="Verse or range to retrieve Dead Sea Scrolls parallels for"),
    service: ResearchService = Depends(_research_service),
) -> DssLinksResponse:
    links = service.fetch_dss_links(osis)
    return DssLinksResponse(
        osis=osis,
        links=[DssLink.model_validate(entry) for entry in links],
        total=len(links),
    )


@router.get("/overview", response_model=ReliabilityOverviewResponse)
def get_reliability_overview(
    osis: str = Query(..., description="Verse to summarise"),
    mode: str | None = Query(
        default=None,
        description="Active study mode such as apologetic or skeptical",
    ),
    service: ResearchService = Depends(_research_service),
) -> ReliabilityOverviewResponse:
    overview = service.build_reliability_overview(osis, mode=mode)
    return ReliabilityOverviewResponse(
        osis=overview.osis,
        mode=overview.mode,
        consensus=[OverviewBullet.model_validate(bullet) for bullet in overview.consensus],
        disputed=[OverviewBullet.model_validate(bullet) for bullet in overview.disputed],
        manuscripts=[OverviewBullet.model_validate(bullet) for bullet in overview.manuscripts],
    )


@router.get("/morphology", response_model=MorphologyResponse)
def get_morphology(
    osis: str = Query(..., description="Verse to fetch morphology for"),
    service: ResearchService = Depends(_research_service),
) -> MorphologyResponse:
    tokens = service.fetch_morphology(osis)
    return MorphologyResponse(
        osis=osis,
        tokens=[MorphToken.model_validate(token) for token in tokens],
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
    service: ResearchService = Depends(_research_service),
) -> ResearchNotesResponse:
    notes = service.list_notes(
        osis,
        stance=stance,
        claim_type=claim_type,
        tag=tag,
        min_confidence=min_confidence,
    )
    return ResearchNotesResponse(
        osis=osis,
        notes=[ResearchNote.model_validate(note) for note in notes],
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
    service: ResearchService = Depends(_research_service),
) -> HistoricitySearchResponse:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise HTTPException(status_code=422, detail="year_from cannot exceed year_to")

    results = service.historicity_search(
        query,
        year_from=year_from,
        year_to=year_to,
        limit=limit,
    )
    return HistoricitySearchResponse(
        query=query,
        results=[HistoricityEntry.model_validate(entry) for entry in results],
        total=len(results),
    )


@router.post("/notes", response_model=ResearchNoteResponse, status_code=201)
def create_note(
    payload: ResearchNoteCreate,
    service: ResearchService = Depends(_research_service),
) -> ResearchNoteResponse:
    if not payload.body.strip():
        raise HTTPException(status_code=422, detail="Note body cannot be empty")

    draft = ResearchNoteDraft(
        osis=payload.osis,
        body=payload.body,
        title=payload.title,
        stance=payload.stance,
        claim_type=payload.claim_type,
        confidence=payload.confidence,
        tags=tuple(payload.tags or []) or None,
        evidences=_to_evidence_drafts(payload.evidences),
    )
    note = service.create_note(draft)
    return ResearchNoteResponse(note=ResearchNote.model_validate(note))


@router.patch("/notes/{note_id}", response_model=ResearchNoteResponse)
def patch_note(
    note_id: str,
    payload: ResearchNoteUpdate,
    service: ResearchService = Depends(_research_service),
) -> ResearchNoteResponse:
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=422, detail="No fields provided for update")

    if "body" in update_data and update_data["body"] is not None:
        if not update_data["body"].strip():
            raise HTTPException(status_code=422, detail="Note body cannot be empty")

    evidence_drafts = None
    if "evidences" in update_data:
        raw_evidences = payload.evidences
        evidence_drafts = _to_evidence_drafts(raw_evidences)
        update_data.pop("evidences", None)
    try:
        note = service.update_note(
            note_id,
            update_data,
            evidences=evidence_drafts,
        )
    except ResearchNoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Research note not found") from exc
    return ResearchNoteResponse(note=ResearchNote.model_validate(note))


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(
    note_id: str,
    service: ResearchService = Depends(_research_service),
) -> Response:
    try:
        service.delete_note(note_id)
    except ResearchNoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Research note not found") from exc
    return Response(status_code=204)


@router.post("/fallacies", response_model=FallacyDetectResponse)
def detect_fallacies(
    payload: FallacyDetectRequest,
    service: ResearchService = Depends(_research_service),
) -> FallacyDetectResponse:
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="Text must not be empty")

    detections = service.fallacy_detect(
        payload.text,
        min_confidence=payload.min_confidence,
    )
    return FallacyDetectResponse(
        text=payload.text,
        detections=[FallacyDetection.model_validate(hit) for hit in detections],
        total=len(detections),
    )


@router.post("/report", response_model=ResearchReportResponse)
def build_report(
    payload: ReportBuildRequest,
    service: ResearchService = Depends(_research_service),
) -> ResearchReportResponse:
    if payload.include_fallacies and not payload.narrative_text:
        raise HTTPException(
            status_code=422,
            detail="narrative_text is required when include_fallacies is true",
        )

    report = service.report_build(
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
    return ResearchReportResponse(report=ResearchReport.model_validate(report))


@router.get("/contradictions", response_model=ContradictionSearchResponse)
def list_contradictions(
    osis: list[str] = Query(..., description="OSIS reference or list of references"),
    topic: str | None = Query(default=None, description="Optional topic tag filter"),
    perspective: list[str] | None = Query(
        default=None,
        description="Filter by interpretive perspective (apologetic, skeptical, neutral)",
    ),
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ContradictionSearchResponse:
    settings = get_settings()
    if not getattr(settings, "contradictions_enabled", True):
        return ContradictionSearchResponse(items=[])

    items = search_contradictions(
        session,
        osis=osis,
        topic=topic,
        perspectives=perspective,
        limit=limit,
    )
    return ContradictionSearchResponse(items=items)


@router.get("/commentaries", response_model=CommentarySearchResponse)
def list_commentaries(
    osis: list[str] = Query(..., description="OSIS reference or list of references"),
    perspective: list[str] | None = Query(
        default=None,
        description="Filter by interpretive perspective (apologetic, skeptical, neutral)",
    ),
    limit: int = Query(default=50, ge=1, le=250),
    session: Session = Depends(get_session),
) -> CommentarySearchResponse:
    excerpts = search_commentaries(
        session,
        osis=osis,
        perspectives=perspective,
        limit=limit,
    )
    anchor = osis[0] if isinstance(osis, list) and osis else osis
    if isinstance(anchor, list):
        anchor = anchor[0] if anchor else ""
    return CommentarySearchResponse(
        osis=str(anchor) if anchor else "",
        items=excerpts,
        total=len(excerpts),
    )


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


@router.get("/geo/verse", response_model=GeoVerseResponse)
def lookup_geo_for_verse(
    osis: str = Query(..., description="OSIS reference to inspect"),
    session: Session = Depends(get_session),
) -> GeoVerseResponse:
    settings = get_settings()
    if not getattr(settings, "geo_enabled", True):
        return GeoVerseResponse(osis=osis)

    return places_for_osis(session, osis)
