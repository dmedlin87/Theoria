"""Intent classification utilities backed by a scikit-learn pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional dependency resolution
    import joblib
except Exception:  # noqa: BLE001 - handled by fail-open logic
    joblib = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency resolution
    from sklearn.pipeline import Pipeline
except Exception:  # noqa: BLE001 - handled by fail-open logic
    Pipeline = Any  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class IntentTag:
    """Structured representation of a classified chat intent."""

    intent: str
    stance: str | None = None
    confidence: float | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a serialisable representation of the tag."""

        payload: dict[str, Any] = {"intent": self.intent}
        if self.stance:
            payload["stance"] = self.stance
        if self.confidence is not None:
            payload["confidence"] = float(self.confidence)
        return payload


class IntentTagger:
    """Wrapper around a scikit-learn pipeline for intent inference."""

    def __init__(self, model_path: Path) -> None:
        self._model_path = Path(model_path)
        self._pipeline: Pipeline | None = None
        self._label_separator: str = "|||"
        self._label_schema: dict[str, Any] = {}

    @property
    def label_schema(self) -> dict[str, Any]:
        """Return the label schema bundled with the model artifact."""

        self._ensure_loaded()
        return self._label_schema

    def predict(self, message: str) -> IntentTag:
        """Predict an intent tag for the provided user message."""

        if not message:
            raise ValueError("message must be provided for intent tagging")

        pipeline = self._ensure_loaded()
        label = pipeline.predict([message])[0]
        intent, stance = self._decode_label(str(label))

        confidence: float | None = None
        try:
            probabilities = pipeline.predict_proba([message])[0]
            classifier = pipeline.named_steps.get("classifier")
            classes = getattr(classifier, "classes_", None)
            if classes is None:
                raise AttributeError("classifier missing classes_ attribute")
            index = list(classes).index(label)
            confidence = float(probabilities[index])
        except Exception:  # noqa: BLE001 - prediction confidence is best-effort
            LOGGER.debug("Intent classifier does not expose calibrated confidence", exc_info=True)

        return IntentTag(intent=intent, stance=stance, confidence=confidence)

    def _decode_label(self, value: str) -> tuple[str, str | None]:
        if self._label_separator in value:
            intent, stance = value.split(self._label_separator, 1)
            return intent, stance or None
        return value, None

    def _ensure_loaded(self) -> Pipeline:
        if joblib is None:
            raise RuntimeError("joblib is required to load intent tagger models")
        if self._pipeline is not None:
            return self._pipeline

        artifact = joblib.load(self._model_path)
        pipeline: Pipeline | None = None
        label_schema: dict[str, Any] = {}
        separator = "|||"
        if isinstance(artifact, dict):
            pipeline = artifact.get("pipeline")
            label_schema = artifact.get("label_schema") or {}
            separator = artifact.get("label_separator", separator)
        else:
            pipeline = artifact

        if pipeline is None:
            raise ValueError("intent model artifact missing pipeline entry")

        if not hasattr(pipeline, "predict"):
            raise TypeError("intent model artifact does not expose predict()")

        self._pipeline = pipeline
        self._label_schema = label_schema
        self._label_separator = separator
        return pipeline


@lru_cache
def _load_tagger(path: str) -> IntentTagger:
    return IntentTagger(Path(path))


def get_intent_tagger(settings: Any) -> IntentTagger | None:
    """Instantiate an intent tagger based on runtime settings."""

    enabled = bool(getattr(settings, "intent_tagger_enabled", False))
    if not enabled:
        return None

    if joblib is None:
        LOGGER.warning("Intent tagger enabled but joblib is not installed")
        return None

    model_path = getattr(settings, "intent_model_path", None)
    if not model_path:
        LOGGER.warning("Intent tagger enabled but no model path configured")
        return None

    path_str = str(Path(model_path))
    try:
        return _load_tagger(path_str)
    except Exception:  # noqa: BLE001 - surface as warning and fall back gracefully
        LOGGER.warning("Failed to load intent tagger from %s", path_str, exc_info=True)
        return None
