from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock
import importlib
from collections.abc import Iterator
from typing import Any, TYPE_CHECKING

import pytest

try:
    fakeredis_aioredis = importlib.import_module("fakeredis.aioredis")
except ModuleNotFoundError:  # pragma: no cover - fallback for type-checking environments
    fakeredis_aioredis = pytest.importorskip("fakeredis.aioredis")

if TYPE_CHECKING:
    from typing import Protocol

    class FakeRedisType(Protocol):  # pragma: no cover - typing helper only
        async def keys(self, pattern: str, *args: object) -> list[str]: ...

        async def get(self, key: str) -> str | None: ...

        async def flushdb(self) -> None: ...

        async def delete(self, *keys: str) -> int: ...

        async def dbsize(self) -> int: ...

        async def set(self, key: str, value: str) -> bool | None: ...

        async def aclose(self) -> None: ...

        def close(self) -> None: ...
else:
    FakeRedisType = Any

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.ai import rag  # noqa: E402  # import after sys.path mutation
from theo.services.api.app.ai.rag import GuardrailError  # noqa: E402
from theo.services.api.app.ai.registry import LLMModel, LLMRegistry  # noqa: E402
from theo.services.api.app.models.search import (  # noqa: E402
    HybridSearchFilters,
    HybridSearchResult,
)


class _DummyClient:
    def __init__(self, completion: str) -> None:
        self.completion = completion
        self.call_count = 0

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
    ) -> str:
        self.call_count += 1
        return self.completion


class _DummyModel(LLMModel):
    def __init__(self, completion: str) -> None:
        super().__init__(
            name="dummy",
            provider="dummy",
            model="dummy-model",
            routing={},
        )
        self.client = _DummyClient(completion)

    def build_client(self) -> _DummyClient:  # type: ignore[override]
        return self.client


def _make_result(
    *,
    meta: dict[str, object] | None = None,
    result_id: str = "passage-1",
    document_id: str = "doc-1",
    document_title: str | None = None,
    text: str = "For God so loved the world",
    snippet: str | None = None,
    osis_ref: str | None = "John.3.16",
    rank: int = 1,
    page_no: int | None = 2,
) -> HybridSearchResult:
    content = text
    snippet_value = snippet if snippet is not None else text
    return HybridSearchResult(
        id=result_id,
        document_id=document_id,
        document_title=document_title,
        text=content,
        snippet=snippet_value,
        osis_ref=osis_ref,
        rank=rank,
        page_no=page_no,
        meta=meta,
    )


@pytest.fixture()
def fake_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeRedisType]:
    fake = fakeredis_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(rag, "_redis_client", fake, raising=False)
    yield fake
    asyncio.run(fake.flushdb())
    try:
        asyncio.run(fake.aclose())
    except AttributeError:  # pragma: no cover - older fakeredis
        fake.close()
    monkeypatch.setattr(rag, "_redis_client", None, raising=False)


def _make_registry(model: _DummyModel) -> LLMRegistry:
    return LLMRegistry(models={model.name: model}, default_model=model.name)


def test_guarded_answer_accepts_valid_completion(fake_cache: FakeRedisType) -> None:
    completion = "Grace-focused summary.\n\nSources: [1] John.3.16 (page 2)"
    model = _DummyModel(completion)
    registry = _make_registry(model)
    session = MagicMock(spec=Session)

    answer = rag._guarded_answer(  # type: ignore[arg-type]
        session,
        question="What does John 3:16 teach?",
        results=[_make_result()],
        registry=registry,
        model_hint=model.name,
        filters=HybridSearchFilters(),
    )

    assert answer.model_output == completion
    assert answer.model_name == model.name
    assert answer.guardrail_profile is None

    keys = asyncio.run(fake_cache.keys("rag:*"))
    assert keys
    payload = asyncio.run(fake_cache.get(keys[0]))
    assert payload is not None
    cached = json.loads(payload)
    assert cached["validation"]["status"] == "passed"
    assert cached["answer"]["model_output"] == completion


def test_guarded_answer_rejects_mismatched_citations(fake_cache: FakeRedisType) -> None:
    completion = "Incorrect.\n\nSources: [1] Luke.1.1 (page 2)"
    model = _DummyModel(completion)
    registry = _make_registry(model)
    session = MagicMock(spec=Session)

    with pytest.raises(GuardrailError):
        rag._guarded_answer(  # type: ignore[arg-type]
            session,
            question="What does John 3:16 teach?",
            results=[_make_result()],
            registry=registry,
            model_hint=model.name,
            filters=HybridSearchFilters(),
        )

    assert asyncio.run(fake_cache.dbsize()) == 0


def test_guarded_answer_requires_osis_reference(
    fake_cache: FakeRedisType,
) -> None:
    completion = "Answer with missing citations.\n\nSources: [1] Unknown"
    model = _DummyModel(completion)
    registry = _make_registry(model)
    session = MagicMock(spec=Session)

    results = [
        _make_result(result_id="passage-1", osis_ref=None, rank=1),
        _make_result(result_id="passage-2", osis_ref=None, rank=2),
    ]

    with pytest.raises(GuardrailError):
        rag._guarded_answer(  # type: ignore[arg-type]
            session,
            question="What does the passage say?",
            results=results,
            registry=registry,
            model_hint=model.name,
            filters=HybridSearchFilters(),
        )

    assert asyncio.run(fake_cache.dbsize()) == 0


def test_guarded_answer_summary_uses_citation_documents(
    fake_cache: FakeRedisType,
) -> None:
    completion = (
        "Layered explanation.\n\n"
        "Sources: [2] John.3.16 (page 2); [3] Rom.5.8 (page 4)"
    )
    model = _DummyModel(completion)
    registry = _make_registry(model)
    session = MagicMock(spec=Session)

    results = [
        _make_result(
            result_id="passage-0",
            document_id="doc-generic",
            document_title="General Resource",
            text="General background information",
            snippet="General background information",
            osis_ref=None,
            rank=1,
            page_no=1,
        ),
        _make_result(
            result_id="passage-1",
            document_id="doc-john",
            document_title="Gospel According to John",
            text="For God so loved the world",
            snippet="For God so loved the world",
            osis_ref="John.3.16",
            rank=2,
            page_no=2,
        ),
        _make_result(
            result_id="passage-2",
            document_id="doc-romans",
            document_title="Epistle to the Romans",
            text="While we were still sinners Christ died for us.",
            snippet="While we were still sinners Christ died for us.",
            osis_ref="Rom.5.8",
            rank=3,
            page_no=4,
        ),
    ]

    answer = rag._guarded_answer(  # type: ignore[arg-type]
        session,
        question="Explain these passages",
        results=results,
        registry=registry,
        model_hint=model.name,
        filters=HybridSearchFilters(),
    )

    summary_lines = answer.summary.splitlines()
    assert summary_lines == [
        "[2] For God so loved the world — Gospel According to John (John.3.16, page 2)",
        "[3] While we were still sinners Christ died for us. — Epistle to the Romans (Rom.5.8, page 4)",
    ]
    assert [citation.index for citation in answer.citations] == [2, 3]
    assert [citation.document_title for citation in answer.citations] == [
        "Gospel According to John",
        "Epistle to the Romans",
    ]


def test_guarded_answer_profile_mismatch_raises_guardrail_error(
    fake_cache: FakeRedisType,
) -> None:
    completion = "Balanced summary.\n\nSources: [1] John.3.16 (page 2)"
    model = _DummyModel(completion)
    registry = _make_registry(model)
    session = MagicMock(spec=Session)

    filters = HybridSearchFilters(theological_tradition="reformed")

    with pytest.raises(GuardrailError):
        rag._guarded_answer(  # type: ignore[arg-type]
            session,
            question="Summarise with a Reformed lens",
            results=[
                _make_result(meta={"theological_tradition": "catholic"})
            ],
            registry=registry,
            model_hint=model.name,
            filters=filters,
        )

    assert asyncio.run(fake_cache.dbsize()) == 0


def test_guarded_answer_profile_match_includes_profile(
    fake_cache: FakeRedisType,
) -> None:
    completion = "Grace summary.\n\nSources: [1] John.3.16 (page 2)"
    model = _DummyModel(completion)
    registry = _make_registry(model)
    session = MagicMock(spec=Session)

    filters = HybridSearchFilters(
        theological_tradition="reformed", topic_domain="soteriology"
    )
    results = [
        _make_result(
            meta={
                "theological_tradition": "Reformed",
                "topic_domains": ["Soteriology", "Christology"],
            }
        )
    ]

    answer = rag._guarded_answer(  # type: ignore[arg-type]
        session,
        question="Summarise the passage with a Reformed soteriology focus",
        results=results,
        registry=registry,
        model_hint=model.name,
        filters=filters,
    )

    assert answer.model_output == completion
    assert answer.guardrail_profile == {
        "theological_tradition": "reformed",
        "topic_domain": "soteriology",
    }


def test_guarded_answer_reuses_cache(fake_cache: FakeRedisType) -> None:
    completion = "Stable answer.\n\nSources: [1] John.3.16 (page 2)"
    model = _DummyModel(completion)
    registry = _make_registry(model)
    session = MagicMock(spec=Session)

    first = rag._guarded_answer(  # type: ignore[arg-type]
        session,
        question="Explain John 3:16",
        results=[_make_result()],
        registry=registry,
        model_hint=model.name,
        filters=HybridSearchFilters(),
    )

    assert model.client.call_count == 1
    assert first.model_output == completion

    second = rag._guarded_answer(  # type: ignore[arg-type]
        session,
        question="Explain John 3:16",
        results=[_make_result()],
        registry=registry,
        model_hint=model.name,
        filters=HybridSearchFilters(),
    )

    assert model.client.call_count == 1, "cached response should skip regeneration"
    assert second.model_output == completion
    assert second.model_name == model.name


def test_guarded_answer_invalidates_stale_cache(
    fake_cache: FakeRedisType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_completion = "Stable answer.\n\nSources: [1] John.3.16 (page 2)"
    refreshed_completion = "Refreshed answer.\n\nSources: [1] John.3.16 (page 2)"
    model = _DummyModel(initial_completion)
    registry = _make_registry(model)
    session = MagicMock(spec=Session)

    events: list[tuple[str, dict[str, object]]] = []

    def record_event(event: str, *, workflow: str, **context: object) -> None:
        events.append((event, {"workflow": workflow, **context}))

    monkeypatch.setattr(rag, "log_workflow_event", record_event)

    deleted_keys: list[str] = []
    original_delete = fake_cache.delete

    async def record_delete(*keys: str) -> int:
        deleted_keys.extend(keys)
        return await original_delete(*keys)

    monkeypatch.setattr(fake_cache, "delete", record_delete)

    # Populate the cache with a valid answer for the current prompt.
    rag._guarded_answer(  # type: ignore[arg-type]
        session,
        question="Explain John 3:16",
        results=[_make_result()],
        registry=registry,
        model_hint=model.name,
        filters=HybridSearchFilters(),
    )

    assert model.client.call_count == 1

    keys = asyncio.run(fake_cache.keys("rag:*"))
    assert keys
    cache_key = keys[0]
    payload_raw = asyncio.run(fake_cache.get(cache_key))
    assert payload_raw is not None
    payload = json.loads(payload_raw)
    payload["answer"]["model_output"] = (
        "Stale answer.\n\nSources: [1] Luke.1.1 (page 9)"
    )
    asyncio.run(fake_cache.set(cache_key, json.dumps(payload)))

    model.client.completion = refreshed_completion
    deleted_keys.clear()
    events.clear()

    refreshed = rag._guarded_answer(  # type: ignore[arg-type]
        session,
        question="Explain John 3:16",
        results=[_make_result()],
        registry=registry,
        model_hint=model.name,
        filters=HybridSearchFilters(),
    )

    assert refreshed.model_output == refreshed_completion
    assert model.client.call_count == 2
    assert cache_key in deleted_keys
    assert any(
        event == "workflow.guardrails_cache" and data.get("status") == "stale"
        for event, data in events
    )

    refreshed_payload_raw = asyncio.run(fake_cache.get(cache_key))
    assert refreshed_payload_raw is not None
    refreshed_payload = json.loads(refreshed_payload_raw)
    assert refreshed_payload["answer"]["model_output"] == refreshed_completion
