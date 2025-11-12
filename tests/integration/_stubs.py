from __future__ import annotations

import asyncio
import sys
import types
from typing import Any, Callable


def install_sklearn_stub() -> None:
    """Install lightweight sklearn replacements used in integration tests."""

    if "sklearn" in sys.modules:
        return

    sklearn_module = types.ModuleType("sklearn")
    ensemble_module = types.ModuleType("sklearn.ensemble")
    cluster_module = types.ModuleType("sklearn.cluster")

    class _StubIsolationForest:
        def __init__(self, *_, **__) -> None:
            return None

        def fit(self, *_args, **_kwargs):
            return self

        def decision_function(self, embeddings):
            return [0.0 for _ in range(len(embeddings) or 0)]

        def predict(self, embeddings):
            return [1 for _ in range(len(embeddings) or 0)]

    ensemble_module.IsolationForest = _StubIsolationForest  # type: ignore[attr-defined]
    sklearn_module.ensemble = ensemble_module  # type: ignore[attr-defined]

    class _StubDBSCAN:
        def __init__(self, *_, **__) -> None:
            return None

        def fit_predict(self, embeddings):
            return [0 for _ in range(len(embeddings) or 0)]

    cluster_module.DBSCAN = _StubDBSCAN  # type: ignore[attr-defined]
    sklearn_module.cluster = cluster_module  # type: ignore[attr-defined]

    sys.modules["sklearn"] = sklearn_module
    sys.modules["sklearn.ensemble"] = ensemble_module
    sys.modules["sklearn.cluster"] = cluster_module


def install_celery_stub() -> None:
    """Install a pared-down Celery facade for environments without the dependency."""

    if "celery" in sys.modules:
        return

    celery_module = types.ModuleType("celery")

    class _StubResult:
        def __init__(self, value: Any = None) -> None:
            self.id = "stub-task-id"
            self.state = "SUCCESS"
            self._value = value

        def ready(self) -> bool:
            return True

        def get(self, *_, **__) -> Any:
            return self._value

    class _StubCelery:
        def __init__(self, *_, **__) -> None:
            self.conf = types.SimpleNamespace(
                task_always_eager=True,
                task_ignore_result=True,
                task_store_eager_result=False,
            )

        def task(self, *args, **kwargs):
            def decorator(func):
                def _delay(*call_args: Any, **call_kwargs: Any) -> _StubResult:
                    if asyncio.iscoroutinefunction(func):
                        coro = func(*call_args, **call_kwargs)
                        try:
                            loop = asyncio.get_running_loop()
                        except RuntimeError:
                            value = asyncio.run(coro)
                        else:
                            if loop.is_running():
                                new_loop = asyncio.new_event_loop()
                                try:
                                    value = new_loop.run_until_complete(coro)
                                finally:
                                    new_loop.close()
                            else:
                                value = loop.run_until_complete(coro)
                    else:
                        value = func(*call_args, **call_kwargs)
                    return _StubResult(value)

                def _apply_async(
                    args: tuple[Any, ...] | None = None,
                    kwargs: dict[str, Any] | None = None,
                    **__params: Any,
                ) -> _StubResult:
                    call_args = args or ()
                    call_kwargs = kwargs or {}
                    return _delay(*call_args, **call_kwargs)

                setattr(func, "delay", _delay)
                setattr(func, "apply_async", _apply_async)
                return func

            return decorator

    celery_module.Celery = _StubCelery  # type: ignore[attr-defined]

    celery_app_module = types.ModuleType("celery.app")
    celery_task_module = types.ModuleType("celery.app.task")

    class _StubTask:
        abstract = False

    celery_task_module.Task = _StubTask  # type: ignore[attr-defined]
    celery_app_module.task = celery_task_module  # type: ignore[attr-defined]

    celery_exceptions_module = types.ModuleType("celery.exceptions")

    class _StubRetry(Exception):
        pass

    celery_exceptions_module.Retry = _StubRetry  # type: ignore[attr-defined]

    celery_schedules_module = types.ModuleType("celery.schedules")

    def _crontab(*_args, **_kwargs):
        return {"type": "crontab"}

    celery_schedules_module.crontab = _crontab  # type: ignore[attr-defined]

    celery_utils_module = types.ModuleType("celery.utils")
    celery_utils_log_module = types.ModuleType("celery.utils.log")

    def _get_task_logger(name: str):
        class _StubLogger:
            def info(self, *_args, **_kwargs):
                return None

            def error(self, *_args, **_kwargs):
                return None

        return _StubLogger()

    celery_utils_log_module.get_task_logger = _get_task_logger  # type: ignore[attr-defined]
    celery_utils_module.log = celery_utils_log_module  # type: ignore[attr-defined]

    sys.modules["celery"] = celery_module
    sys.modules["celery.app"] = celery_app_module
    sys.modules["celery.app.task"] = celery_task_module
    sys.modules["celery.exceptions"] = celery_exceptions_module
    sys.modules["celery.schedules"] = celery_schedules_module
    sys.modules["celery.utils"] = celery_utils_module
    sys.modules["celery.utils.log"] = celery_utils_log_module

    celery_result_module = types.ModuleType("celery.result")

    celery_result_module.AsyncResult = _StubResult  # type: ignore[attr-defined]
    sys.modules["celery.result"] = celery_result_module


def install_audio_stubs() -> None:
    """Provide deterministic Whisper/transfomer replacements for tests."""

    if "whisper" not in sys.modules:
        whisper_module = types.ModuleType("whisper")

        class _StubWhisperModel:
            def transcribe(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
                return {
                    "segments": [
                        {
                            "start": 0.0,
                            "end": 3.5,
                            "text": "Stub transcript referencing Gen.1.1 for duplicate checks.",
                            "no_speech_prob": 0.0,
                        }
                    ]
                }

        def _load_model(*_args: Any, **_kwargs: Any) -> _StubWhisperModel:
            return _StubWhisperModel()

        whisper_module.load_model = _load_model  # type: ignore[attr-defined]
        sys.modules["whisper"] = whisper_module

    if "transformers" not in sys.modules:
        transformers_module = types.ModuleType("transformers")

        def _pipeline(task_name: str, *_, **__) -> Callable[[str], list[dict[str, Any]]]:
            def _run(_text: str) -> list[dict[str, Any]]:
                if task_name == "token-classification":
                    return [
                        {
                            "entity_group": "VERSE",
                            "word": "Gen.1.1",
                            "score": 0.99,
                            "start": 0,
                            "end": 7,
                        }
                    ]
                return []

            return _run

        transformers_module.pipeline = _pipeline  # type: ignore[attr-defined]
        sys.modules["transformers"] = transformers_module


def install_openai_stub() -> None:
    """Install a minimal OpenAI client facade returning canned responses."""

    if "openai" in sys.modules:
        return

    openai_module = types.ModuleType("openai")

    class _StubMessage:
        def __init__(self, content: str) -> None:
            self.content = content

    class _StubDelta:
        def __init__(self, content: str) -> None:
            self.content = content

    class _StubChoice:
        def __init__(self, content: str) -> None:
            self.message = _StubMessage(content)
            self.delta = _StubDelta(content)

    class _StubResponse:
        def __init__(self, content: str) -> None:
            self.choices = [_StubChoice(content)]

    class _StubAsyncStream:
        def __init__(self, content: str) -> None:
            self._content = content

        def __aiter__(self):
            async def _generator():
                yield _StubResponse(self._content)

            return _generator()

    class _StubChatCompletions:
        def __init__(self) -> None:
            self._default = "Stub completion"

        async def create(self, *_, **kwargs: Any):
            messages = kwargs.get("messages") or []
            if messages:
                last = messages[-1]
                content = str(last.get("content") or self._default)
            else:
                content = self._default
            if kwargs.get("stream"):
                return _StubAsyncStream(content)
            return _StubResponse(content)

    class _StubChat:
        def __init__(self) -> None:
            self.completions = _StubChatCompletions()

    class AsyncOpenAI:
        def __init__(self, *_, **__) -> None:
            self.chat = _StubChat()

    openai_module.AsyncOpenAI = AsyncOpenAI  # type: ignore[attr-defined]
    sys.modules["openai"] = openai_module


def install_duplicate_detection_stub() -> None:
    """Install a placeholder duplicate detector when optional extras are absent."""

    module_name = "theo.infrastructure.api.app.ingest.duplicate_detector"
    if module_name in sys.modules:
        return

    duplicate_module = types.ModuleType(module_name)

    class _StubDuplicateDetector:
        def check(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
            return []

        def record(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    duplicate_module.DuplicateDetector = _StubDuplicateDetector  # type: ignore[attr-defined]
    sys.modules[module_name] = duplicate_module


__all__ = [
    "install_audio_stubs",
    "install_celery_stub",
    "install_duplicate_detection_stub",
    "install_openai_stub",
    "install_sklearn_stub",
]
