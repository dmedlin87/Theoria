"""Reader + research dock endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.settings import get_settings
from ..models.research import (
    ContradictionSearchResponse,
    CrossReferenceResponse,
    GeoPlaceSearchResponse,
    MorphologyResponse,
    ResearchNoteCreate,
    ResearchNoteResponse,
    ResearchNotesResponse,
    ResearchNoteUpdate,
    ScriptureResponse,
)
from ..research import (
    create_research_note,
    delete_research_note,
    fetch_cross_references,
    fetch_morphology,
    fetch_passage,
    get_notes_for_osis,
    update_research_note,
    lookup_geo_places,
    search_contradictions,
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
    session: Session = Depends(get_session),
) -> ResearchNotesResponse:
    notes = get_notes_for_osis(session, osis)
    return ResearchNotesResponse(
        osis=osis,
        notes=notes,
        total=len(notes),
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
