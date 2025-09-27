from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest
from fakeredis import aioredis as fakeredis_aioredis
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.ai import rag  # noqa: E402  # import after sys.path mutation
from theo.services.api.app.ai.rag import GuardrailError  # noqa: E402
from theo.services.api.app.ai.registry import LLMRegistry  # noqa: E402
from theo.services.api.app.models.search import HybridSearchResult  # noqa: E402


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


class _DummyModel:
    def __init__(self, completion: str) -> None:
        self.name = "dummy"
        self.model = "dummy-model"
        self.client = _DummyClient(completion)

    def build_client(self) -> _DummyClient:
        return self.client


def _make_result() -> HybridSearchResult:
    return HybridSearchResult(
        id="passage-1",
        document_id="doc-1",
        text="For God so loved the world",
        snippet="For God so loved the world",
        osis_ref="John.3.16",
        rank=1,
        page_no=2,
    )


@pytest.fixture()
def fake_cache(monkeypatch: pytest.MonkeyPatch) -> fakeredis_aioredis.FakeRedis:
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


def test_guarded_answer_accepts_valid_completion(fake_cache: fakeredis_aioredis.FakeRedis) -> None:
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
    )

    assert answer.model_output == completion
    assert answer.model_name == model.name

    keys = asyncio.run(fake_cache.keys("rag:*"))
    assert keys
    payload = asyncio.run(fake_cache.get(keys[0]))
    assert payload is not None
    cached = json.loads(payload)
    assert cached["validation"]["status"] == "passed"
    assert cached["answer"]["model_output"] == completion


def test_guarded_answer_rejects_mismatched_citations(fake_cache: fakeredis_aioredis.FakeRedis) -> None:
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
        )

    assert asyncio.run(fake_cache.dbsize()) == 0


def test_guarded_answer_reuses_cache(fake_cache: fakeredis_aioredis.FakeRedis) -> None:
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
    )

    assert model.client.call_count == 1
    assert first.model_output == completion

    second = rag._guarded_answer(  # type: ignore[arg-type]
        session,
        question="Explain John 3:16",
        results=[_make_result()],
        registry=registry,
        model_hint=model.name,
    )

    assert model.client.call_count == 1, "cached response should skip regeneration"
    assert second.model_output == completion
    assert second.model_name == model.name
