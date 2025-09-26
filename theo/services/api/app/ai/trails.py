"""Persistence helpers for agent research trails."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..db.models import AgentStep, AgentTrail, TrailSource
from ..models.search import HybridSearchFilters


def _normalize_payload(value: Any) -> Any:
    """Convert nested Pydantic models or dataclasses into plain dicts."""

    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[no-any-return]
    if isinstance(value, Mapping):
        return {key: _normalize_payload(val) for key, val in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_payload(item) for item in value]
    return value


@dataclass
class TrailReplayResult:
    """Result payload and diff metadata returned when replaying a trail."""

    output: Any
    diff: dict[str, Any]


class TrailRecorder:
    """Context manager that records steps and sources for an agent trail."""

    def __init__(self, session: Session, trail: AgentTrail) -> None:
        self._session = session
        self.trail = trail
        self._next_step_index = len(trail.steps)
        self._finalized = False

    def __enter__(self) -> "TrailRecorder":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # type: ignore[override]
        if exc_type is not None and not self._finalized:
            message = str(exc) if exc else exc_type.__name__
            self.fail(message)
        return False

    def log_step(
        self,
        *,
        tool: str,
        action: str | None = None,
        status: str = "completed",
        input_payload: Any = None,
        output_payload: Any = None,
        output_digest: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        error_message: str | None = None,
    ) -> AgentStep:
        step = AgentStep(
            trail_id=self.trail.id,
            step_index=self._next_step_index,
            tool=tool,
            action=action,
            status=status,
            input_payload=_normalize_payload(input_payload),
            output_payload=_normalize_payload(output_payload),
            output_digest=output_digest,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            error_message=error_message,
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC) if status == "completed" else None,
        )
        self._next_step_index += 1
        self.trail.steps.append(step)
        self._session.add(step)
        self._session.flush()
        return step

    def add_source(
        self,
        *,
        source_type: str,
        reference: str,
        meta: Mapping[str, Any] | None = None,
    ) -> TrailSource:
        source = TrailSource(
            trail_id=self.trail.id,
            source_type=source_type,
            reference=reference,
            meta=_normalize_payload(meta),
        )
        self.trail.sources.append(source)
        self._session.add(source)
        self._session.flush()
        return source

    def record_citations(self, citations: Sequence[Any]) -> None:
        for citation in citations:
            if citation is None:
                continue
            reference = getattr(citation, "passage_id", None) or getattr(
                citation, "document_id", None
            )
            if not reference:
                continue
            meta = {
                "osis": getattr(citation, "osis", None),
                "anchor": getattr(citation, "anchor", None),
                "document_id": getattr(citation, "document_id", None),
                "snippet": getattr(citation, "snippet", None),
            }
            self.add_source(source_type="passage", reference=str(reference), meta=meta)

    def finalize(
        self,
        *,
        final_md: str | None = None,
        output_payload: Any = None,
        status: str = "completed",
    ) -> AgentTrail:
        self.trail.status = status
        self.trail.final_md = final_md
        self.trail.output_payload = _normalize_payload(output_payload)
        self.trail.error_message = None
        self.trail.completed_at = datetime.now(UTC)
        self.trail.updated_at = datetime.now(UTC)
        self._session.add(self.trail)
        self._session.commit()
        self._finalized = True
        return self.trail

    def fail(self, message: str) -> AgentTrail:
        self.trail.status = "failed"
        self.trail.error_message = message
        self.trail.completed_at = datetime.now(UTC)
        self.trail.updated_at = datetime.now(UTC)
        self._session.add(self.trail)
        self._session.commit()
        self._finalized = True
        return self.trail


class TrailService:
    """High-level API for persisting and replaying agent trails."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def start_trail(
        self,
        *,
        workflow: str,
        plan_md: str | None,
        mode: str | None,
        input_payload: Any,
        user_id: str | None = None,
    ) -> TrailRecorder:
        trail = AgentTrail(
            workflow=workflow,
            mode=mode,
            user_id=user_id,
            plan_md=plan_md,
            status="running",
            input_payload=_normalize_payload(input_payload),
            started_at=datetime.now(UTC),
        )
        self._session.add(trail)
        self._session.flush()
        return TrailRecorder(self._session, trail)

    def get_trail(self, trail_id: str) -> AgentTrail | None:
        return self._session.get(AgentTrail, trail_id)

    def replay_trail(
        self,
        trail: AgentTrail,
        *,
        model_override: str | None = None,
    ) -> TrailReplayResult:
        payload = _normalize_payload(trail.input_payload) or {}
        if not isinstance(payload, Mapping):
            raise ValueError("trail input payload must be a mapping")
        mutable_payload = dict(payload)
        if model_override:
            mutable_payload["model"] = model_override

        workflow = trail.workflow
        if workflow == "verse_copilot":
            response = self._replay_verse_copilot(mutable_payload)
        elif workflow == "sermon_prep":
            response = self._replay_sermon_prep(mutable_payload)
        else:
            raise ValueError(f"Replay not implemented for workflow '{workflow}'")

        output_payload = _normalize_payload(response)
        diff = self._build_diff(trail.output_payload, output_payload)
        trail.last_replayed_at = datetime.now(UTC)
        self._session.add(trail)
        self._session.commit()
        return TrailReplayResult(output=response, diff=diff)

    def _replay_verse_copilot(self, payload: Mapping[str, Any]) -> Any:
        from .rag import generate_verse_brief  # Local import to avoid cycle

        osis = payload.get("osis")
        if not isinstance(osis, str):
            raise ValueError("Stored payload missing 'osis'")
        question = (
            payload.get("question")
            if isinstance(payload.get("question"), str)
            else None
        )
        filters_payload = payload.get("filters")
        filters = None
        if isinstance(filters_payload, Mapping):
            filters = HybridSearchFilters(**dict(filters_payload))
        model_name = (
            payload.get("model") if isinstance(payload.get("model"), str) else None
        )
        return generate_verse_brief(
            self._session,
            osis=osis,
            question=question,
            filters=filters,
            model_name=model_name,
        )

    def _replay_sermon_prep(self, payload: Mapping[str, Any]) -> Any:
        from .rag import generate_sermon_prep_outline  # Local import to avoid cycle

        topic = payload.get("topic")
        if not isinstance(topic, str):
            raise ValueError("Stored payload missing 'topic'")
        osis = payload.get("osis") if isinstance(payload.get("osis"), str) else None
        filters_payload = payload.get("filters")
        filters = None
        if isinstance(filters_payload, Mapping):
            filters = HybridSearchFilters(**dict(filters_payload))
        model_name = (
            payload.get("model") if isinstance(payload.get("model"), str) else None
        )
        return generate_sermon_prep_outline(
            self._session,
            topic=topic,
            osis=osis,
            filters=filters,
            model_name=model_name,
        )

    def _build_diff(self, previous: Any, current: Any) -> dict[str, Any]:
        previous_payload = _normalize_payload(previous) or {}
        current_payload = _normalize_payload(current) or {}
        diff: dict[str, Any] = {
            "changed": previous_payload != current_payload,
            "summary_changed": self._extract_summary(previous_payload)
            != self._extract_summary(current_payload),
        }
        prev_citations = self._extract_citation_refs(previous_payload)
        new_citations = self._extract_citation_refs(current_payload)
        diff["added_citations"] = sorted(new_citations - prev_citations)
        diff["removed_citations"] = sorted(prev_citations - new_citations)
        return diff

    @staticmethod
    def _extract_summary(payload: Mapping[str, Any]) -> str | None:
        answer = payload.get("answer") if isinstance(payload, Mapping) else None
        if isinstance(answer, Mapping):
            summary = answer.get("summary")
            if isinstance(summary, str):
                return summary
        return None

    @staticmethod
    def _extract_citation_refs(payload: Mapping[str, Any]) -> set[str]:
        citations: set[str] = set()
        answer = payload.get("answer") if isinstance(payload, Mapping) else None
        if isinstance(answer, Mapping):
            raw_citations = answer.get("citations")
            if isinstance(raw_citations, Sequence):
                for item in raw_citations:
                    if not isinstance(item, Mapping):
                        continue
                    reference = item.get("passage_id") or item.get("document_id")
                    osis = item.get("osis")
                    if isinstance(reference, str):
                        key = reference
                        if isinstance(osis, str):
                            key = f"{reference}:{osis}"
                        citations.add(key)
        return citations


__all__ = ["TrailService", "TrailRecorder", "TrailReplayResult"]
