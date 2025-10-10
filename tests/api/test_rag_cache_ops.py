from unittest.mock import MagicMock

from theo.services.api.app.ai.rag.cache_ops import build_cache_key, load_cached_answer, store_cached_answer
from theo.services.api.app.ai.rag.models import RAGAnswer


class _FakeCache:
    def __init__(self) -> None:
        self.stored: dict[str, tuple[RAGAnswer, dict | None]] = {}

    def build_key(self, *, user_id, model_label, prompt, retrieval_digest):
        return f"{user_id}:{model_label}:{retrieval_digest}:{len(prompt)}"

    def load(self, key: str):
        return self.stored.get(key)

    def store(self, key: str, *, answer: RAGAnswer, validation):
        self.stored[key] = (answer, validation)


def test_build_cache_key_uses_injected_cache() -> None:
    cache = _FakeCache()
    key = build_cache_key(
        user_id="user-1",
        model_label="model-x",
        prompt="hello",
        retrieval_digest="digest",
        cache=cache,
    )
    assert key == "user-1:model-x:digest:5"


def test_store_and_load_cached_answer_round_trip() -> None:
    cache = _FakeCache()
    answer = RAGAnswer(summary="hi", citations=[], model_name="m", model_output="out")
    store_cached_answer("key", answer=answer, validation={"status": "passed"}, cache=cache)

    loaded = load_cached_answer("key", cache=cache)
    assert loaded == (answer, {"status": "passed"})
