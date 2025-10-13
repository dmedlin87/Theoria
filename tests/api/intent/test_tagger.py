"""Tests for the intent tagger utilities."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from theo.services.api.app.intent import tagger as intent_tagger


class _StubPipeline:
    """Lightweight pipeline implementation used for tests."""

    def __init__(
        self,
        *,
        label: str,
        probabilities: list[float],
        classes: list[str] | None = None,
    ) -> None:
        self._label = label
        self._probabilities = probabilities
        class_labels = classes or [label, "fallback"][: len(probabilities)]
        self.named_steps = {
            "classifier": SimpleNamespace(classes_=class_labels),
        }

    def predict(self, messages: list[str]) -> list[str]:  # pragma: no cover - exercised in tests
        assert messages, "predict should receive at least one message"
        return [self._label]

    def predict_proba(self, messages: list[str]) -> list[list[float]]:
        assert messages, "predict_proba should receive at least one message"
        return [self._probabilities]


def _patch_joblib(monkeypatch: pytest.MonkeyPatch, artifact: object) -> None:
    """Patch the tagger module's joblib reference with a stub loader."""

    class _StubJoblib:
        def __init__(self) -> None:
            self.calls: list[object] = []

        def load(self, path: object) -> object:  # pragma: no cover - trivial
            self.calls.append(path)
            return artifact

    monkeypatch.setattr(intent_tagger, "joblib", _StubJoblib())


def test_predict_returns_structured_tag_with_confidence(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """IntentTagger.predict should decode labels and surface confidence."""

    label = "purchase::positive"
    classes = ["fallback", label]
    pipeline = _StubPipeline(label=label, probabilities=[0.13, 0.87], classes=classes)
    artifact = {
        "pipeline": pipeline,
        "label_schema": {"purchase": {"stance": ["positive"]}},
        "label_separator": "::",
    }
    _patch_joblib(monkeypatch, artifact)

    tagger = intent_tagger.IntentTagger(tmp_path / "model.joblib")

    result = tagger.predict("please help me buy this")

    assert isinstance(result, intent_tagger.IntentTag)
    assert result.intent == "purchase"
    assert result.stance == "positive"
    assert result.confidence == pytest.approx(0.87)
    assert tagger.label_schema == artifact["label_schema"]


def test_intent_tag_to_payload_includes_optional_fields() -> None:
    tag = intent_tagger.IntentTag(intent="support", stance="affirm", confidence=0.42)

    assert tag.to_payload() == {
        "intent": "support",
        "stance": "affirm",
        "confidence": 0.42,
    }


def test_decode_label_handles_separator_and_empty_stance(tmp_path) -> None:
    tagger = intent_tagger.IntentTagger(tmp_path / "model.joblib")
    tagger._label_separator = "::"

    intent, stance = tagger._decode_label("support::dissent::partial")
    assert intent == "support"
    assert stance == "dissent::partial"

    intent, stance = tagger._decode_label("support::")
    assert intent == "support"
    assert stance is None

    intent, stance = tagger._decode_label("support")
    assert intent == "support"
    assert stance is None


def test_ensure_loaded_with_dict_artifact_caches_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    pipeline = _StubPipeline(label="support|||affirm", probabilities=[1.0])
    artifact = {
        "pipeline": pipeline,
        "label_schema": {"support": {}},
        "label_separator": "::",
    }

    calls: list[object] = []

    class _RecordingJoblib:
        def load(self, path: object) -> object:  # pragma: no cover - trivial
            calls.append(path)
            return artifact

    monkeypatch.setattr(intent_tagger, "joblib", _RecordingJoblib())

    tagger = intent_tagger.IntentTagger(tmp_path / "model.joblib")

    loaded_pipeline = tagger._ensure_loaded()
    assert loaded_pipeline is pipeline
    assert tagger.label_schema == artifact["label_schema"]
    assert tagger._label_separator == "::"

    # Subsequent calls should use the cached pipeline without reloading
    second_call = tagger._ensure_loaded()
    assert second_call is pipeline
    assert len(calls) == 1


def test_ensure_loaded_accepts_pipeline_objects(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    pipeline = _StubPipeline(label="support", probabilities=[1.0])
    _patch_joblib(monkeypatch, pipeline)

    tagger = intent_tagger.IntentTagger(tmp_path / "model.joblib")

    assert tagger._ensure_loaded() is pipeline
    assert tagger.label_schema == {}


def test_ensure_loaded_requires_predict(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    artifact = {"pipeline": SimpleNamespace()}  # missing predict attribute
    _patch_joblib(monkeypatch, artifact)

    tagger = intent_tagger.IntentTagger(tmp_path / "model.joblib")

    with pytest.raises(TypeError):
        tagger._ensure_loaded()


def test_get_intent_tagger_respects_feature_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(intent_tagger, "joblib", SimpleNamespace(load=lambda _: None))

    settings = SimpleNamespace(intent_tagger_enabled=False, intent_model_path="ignored.joblib")

    assert intent_tagger.get_intent_tagger(settings) is None


def test_get_intent_tagger_warns_when_joblib_missing(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(intent_tagger, "joblib", None)
    settings = SimpleNamespace(intent_tagger_enabled=True, intent_model_path="model.joblib")

    with caplog.at_level(logging.WARNING):
        assert intent_tagger.get_intent_tagger(settings) is None

    assert "joblib is not installed" in caplog.text


def test_get_intent_tagger_warns_when_path_missing(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(intent_tagger, "joblib", SimpleNamespace(load=lambda _: None))
    settings = SimpleNamespace(intent_tagger_enabled=True, intent_model_path=None)

    with caplog.at_level(logging.WARNING):
        assert intent_tagger.get_intent_tagger(settings) is None

    assert "no model path configured" in caplog.text


def test_get_intent_tagger_handles_loading_errors(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(intent_tagger, "joblib", SimpleNamespace(load=lambda _: None))

    def _failing_loader(path: str) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(intent_tagger, "_load_tagger", _failing_loader)

    settings = SimpleNamespace(intent_tagger_enabled=True, intent_model_path="model.joblib")

    with caplog.at_level(logging.WARNING):
        assert intent_tagger.get_intent_tagger(settings) is None

    assert "Failed to load intent tagger" in caplog.text


def test_get_intent_tagger_returns_loaded_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(intent_tagger, "joblib", SimpleNamespace(load=lambda _: None))

    expected = object()

    def _successful_loader(path: str) -> object:
        assert path.endswith("model.joblib")
        return expected

    monkeypatch.setattr(intent_tagger, "_load_tagger", _successful_loader)

    settings = SimpleNamespace(intent_tagger_enabled=True, intent_model_path="/tmp/model.joblib")

    assert intent_tagger.get_intent_tagger(settings) is expected

