"""Routes exposing agent research trails and replay functionality."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..ai.trails import TrailService
from ..core.database import get_session
from ..models.trails import (
    AgentTrail,
    TrailReplayDiff,
    TrailReplayRequest,
    TrailReplayResponse,
)

router = APIRouter()


@router.get("/{trail_id}", response_model=AgentTrail, response_model_exclude_none=True)
def get_trail(trail_id: str, session: Session = Depends(get_session)) -> AgentTrail:
    service = TrailService(session)
    trail = service.get_trail(trail_id)
    if trail is None:
        raise HTTPException(status_code=404, detail="Trail not found")
    return AgentTrail.model_validate(trail)


@router.post(
    "/{trail_id}/replay",
    response_model=TrailReplayResponse,
    response_model_exclude_none=True,
)
def replay_trail(
    trail_id: str,
    payload: TrailReplayRequest | None = None,
    session: Session = Depends(get_session),
) -> TrailReplayResponse:
    service = TrailService(session)
    trail = service.get_trail(trail_id)
    if trail is None:
        raise HTTPException(status_code=404, detail="Trail not found")
    request = payload or TrailReplayRequest()
    result = service.replay_trail(trail, model_override=request.model)
    replay_output = result.output
    if hasattr(replay_output, "model_dump"):
        replay_payload = replay_output.model_dump(mode="json")  # type: ignore[assignment]
    else:
        replay_payload = replay_output
    diff = TrailReplayDiff(**result.diff)
    return TrailReplayResponse(
        trail_id=trail.id,
        original_output=trail.output_payload,
        replay_output=replay_payload,
        diff=diff,
    )


__all__ = ["router"]
