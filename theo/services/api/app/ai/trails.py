"""Persistence helpers for agent research trails."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy.orm import Session

from theo.adapters.persistence.models import (
    AgentStep,
    AgentTrail,
    TrailRetrievalSnapshot,
    TrailSource,
)
from ..models.search import HybridSearchFilters


LOGGER = logging.getLogger(__name__)


def _dedupe_and_clean(values: Sequence[Any]) -> list[str]:
    """Normalise a sequence of raw values into a unique ordered list of strings."""

    ordered: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in ordered:
            continue
        ordered.append(text)
    return ordered


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


def _maybe_build_digest(payload: Any) -> TrailStepDigest | None:
    normalised = _normalize_payload(payload)
    if not isinstance(normalised, Mapping):
        return None
    summary: str | None = None
    if "summary" in normalised and isinstance(normalised.get("summary"), str):
        summary = normalised.get("summary")
    elif "answer" in normalised and isinstance(normalised.get("answer"), Mapping):
        answer_mapping = normalised["answer"]
        summary_val = answer_mapping.get("summary")
        if isinstance(summary_val, str):
            summary = summary_val
    if not summary:
        return None
    key_entities = normalised.get("key_entities")
    recommended = normalised.get("recommended_actions")
    mapping: dict[str, Any] = {
        "summary": summary,
    }
    if isinstance(key_entities, Sequence):
        mapping["key_entities"] = key_entities
    if isinstance(recommended, Sequence):
        mapping["recommended_actions"] = recommended
    return TrailStepDigest.from_mapping(mapping)


@dataclass
class TrailStepDigest:
    """Structured summary of a significant trail step."""

    summary: str
    key_entities: Sequence[str] = field(default_factory=tuple)
    recommended_actions: Sequence[str] = field(default_factory=tuple)

    def normalised_key_entities(self) -> list[str]:
        return _dedupe_and_clean(self.key_entities)

    def normalised_recommended_actions(self) -> list[str]:
        return _dedupe_and_clean(self.recommended_actions)

    def digest_hash(self) -> str:
        canonical = "\n".join(
            [
                self.summary.strip(),
                "|".join(self.normalised_key_entities()),
                "|".join(self.normalised_recommended_actions()),
            ]
        )
        return sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "TrailStepDigest":
        summary = str(data.get("summary", "")).strip()
        key_entities = data.get("key_entities")
        recommended = data.get("recommended_actions")
        if isinstance(key_entities, Sequence) and not isinstance(
            key_entities, (str, bytes, bytearray)
        ):
            key_seq: Sequence[str] = key_entities
        else:
            key_seq = ()
        if isinstance(recommended, Sequence) and not isinstance(
            recommended, (str, bytes, bytearray)
        ):
            recommended_seq: Sequence[str] = recommended
        else:
            recommended_seq = ()
        return cls(
            summary=summary,
            key_entities=key_seq,
            recommended_actions=recommended_seq,
        )


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
        existing_turns = [
            snapshot.turn_index
            for snapshot in getattr(trail, "retrieval_snapshots", [])
            if snapshot.turn_index is not None
        ]
        self._next_snapshot_index = (max(existing_turns) + 1) if existing_turns else 0
        self._finalized = False
        self._pending_digests: list[tuple[AgentStep, TrailStepDigest]] = []

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
        digest: TrailStepDigest | Mapping[str, Any] | None = None,
        significant: bool = False,
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
        if digest is not None and status == "completed":
            structured = (
                digest
                if isinstance(digest, TrailStepDigest)
                else TrailStepDigest.from_mapping(dict(digest))
            )
            if structured.summary or structured.key_entities or structured.recommended_actions:
                self._pending_digests.append((step, structured))
        elif significant and status == "completed" and output_payload:
            payload_digest = _maybe_build_digest(output_payload)
            if payload_digest is not None:
                self._pending_digests.append((step, payload_digest))
        return step

    def _dispatch_digests(self) -> None:
        if not self._pending_digests:
            return
        try:
            from .trails_memory_bridge import TrailsMemoryBridge
        except Exception:  # pragma: no cover - defensive import guard
            LOGGER.debug("Unable to import trails memory bridge", exc_info=True)
            self._pending_digests.clear()
            return

        bridge = TrailsMemoryBridge(self._session)
        for step, digest in list(self._pending_digests):
            try:
                bridge.record_digest(trail=self.trail, step=step, digest=digest)
            except Exception:  # pragma: no cover - defensive logging
                LOGGER.debug("Failed to persist trail digest", exc_info=True)
        self._pending_digests.clear()

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

    def record_retrieval_snapshot(
        self,
        *,
        retrieval_hash: str,
        passage_ids: Sequence[str] | None = None,
        osis_refs: Sequence[str] | None = None,
        step: AgentStep | None = None,
    ) -> TrailRetrievalSnapshot:
        if not retrieval_hash:
            raise ValueError("retrieval_hash must be provided")

        def _normalise_list(values: Sequence[str] | None) -> list[str]:
            ordered: list[str] = []
            if not values:
                return ordered
            for value in values:
                text = str(value).strip()
                if not text or text in ordered:
                    continue
                ordered.append(text)
            return ordered

        snapshot = TrailRetrievalSnapshot(
            trail_id=self.trail.id,
            turn_index=self._next_snapshot_index,
            retrieval_hash=retrieval_hash,
            passage_ids=_normalise_list(passage_ids),
            osis_refs=_normalise_list(osis_refs),
        )
        if step is not None:
            snapshot.step = step
        self._next_snapshot_index += 1
        self.trail.retrieval_snapshots.append(snapshot)
        self._session.add(snapshot)
        self._session.flush()
        return snapshot

    def finalize(
        self,
        *,
        final_md: str | None = None,
        output_payload: Any = None,
        status: str = "completed",
    ) -> AgentTrail:
        # Ensure any accumulated digests are persisted before we commit the trail
        # updates.  This allows downstream bridges (such as the chat session
        # memory bridge) to write to the same session within the current
        # transaction.
        self._dispatch_digests()

        self.trail.status = status
        self.trail.final_md = final_md
        self.trail.output_payload = _normalize_payload(output_payload)
        self.trail.error_message = None
        now = datetime.now(UTC)
        if status in {"completed", "failed"}:
            self.trail.completed_at = now
        else:
            self.trail.completed_at = None
        self.trail.updated_at = now
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
        self._pending_digests.clear()
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

    def resume_trail(
        self, trail: AgentTrail | str, *, user_id: str | None = None
    ) -> TrailRecorder:
        if isinstance(trail, AgentTrail):
            record = trail
        else:
            record = self.get_trail(trail)
        if record is None:
            raise ValueError("trail not found")
        if user_id and not record.user_id:
            record.user_id = user_id
        record.status = "running"
        record.completed_at = None
        record.updated_at = datetime.now(UTC)
        self._session.add(record)
        self._session.flush()
        return TrailRecorder(self._session, record)

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


__all__ = ["TrailService", "TrailRecorder", "TrailReplayResult", "TrailStepDigest"]
