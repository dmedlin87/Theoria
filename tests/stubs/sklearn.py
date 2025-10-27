"""Sklearn shims for environments without the dependency installed."""

from __future__ import annotations

from types import ModuleType
from typing import Iterable

__all__ = ["build_sklearn_stubs"]


def build_sklearn_stubs() -> dict[str, ModuleType]:
    if "sklearn" in globals():  # pragma: no cover - defensive cache
        raise RuntimeError("sklearn stub module should not be imported as a package")

    sklearn_module = ModuleType("sklearn")

    sklearn_ensemble = ModuleType("sklearn.ensemble")

    class _StubIsolationForest:
        def __init__(self, *_, **__):
            self._scores: list[float] | None = None

        def fit(self, embeddings: Iterable[Iterable[float]] | None):
            count = len(list(embeddings or ()))
            self._scores = [-0.1 for _ in range(count)]
            return self

        def decision_function(self, embeddings: Iterable[Iterable[float]] | None):
            scores = self._scores or [-0.1 for _ in range(len(list(embeddings or ())))]
            return scores

        def predict(self, embeddings: Iterable[Iterable[float]] | None):
            return [-1 for _ in range(len(list(embeddings or ())))]

    sklearn_ensemble.IsolationForest = _StubIsolationForest  # type: ignore[attr-defined]
    sklearn_module.ensemble = sklearn_ensemble  # type: ignore[attr-defined]

    sklearn_cluster = ModuleType("sklearn.cluster")

    class _StubDBSCAN:
        def __init__(self, *_, **__):
            pass

        def fit_predict(self, points):
            return [0 for _ in range(len(points) or 0)]

    sklearn_cluster.DBSCAN = _StubDBSCAN  # type: ignore[attr-defined]
    sklearn_module.cluster = sklearn_cluster  # type: ignore[attr-defined]

    sklearn_pipeline = ModuleType("sklearn.pipeline")

    class _StubPipeline:
        def __init__(self, steps, **_):
            self.steps = steps

        def fit(self, *_args, **_kwargs):
            return self

        def predict(self, data):
            return [0 for _ in range(len(data) or 0)]

        def transform(self, data):
            return data

    sklearn_pipeline.Pipeline = _StubPipeline  # type: ignore[attr-defined]
    sklearn_module.pipeline = sklearn_pipeline  # type: ignore[attr-defined]

    sklearn_feature = ModuleType("sklearn.feature_extraction")
    sklearn_feature_text = ModuleType("sklearn.feature_extraction.text")

    class _StubTfidfVectorizer:
        def __init__(self, *_, **__):
            pass

        def fit(self, *_args, **_kwargs):
            return self

        def transform(self, data):
            return data

        def fit_transform(self, data, *_, **__):
            return data

    sklearn_feature_text.TfidfVectorizer = _StubTfidfVectorizer  # type: ignore[attr-defined]
    sklearn_feature.text = sklearn_feature_text  # type: ignore[attr-defined]
    sklearn_module.feature_extraction = sklearn_feature  # type: ignore[attr-defined]

    sklearn_linear = ModuleType("sklearn.linear_model")

    class _StubLogisticRegression:
        def __init__(self, *_, **__):
            pass

        def fit(self, *_args, **_kwargs):
            return self

        def predict(self, data):
            return [0 for _ in range(len(data) or 0)]

    sklearn_linear.LogisticRegression = _StubLogisticRegression  # type: ignore[attr-defined]
    sklearn_module.linear_model = sklearn_linear  # type: ignore[attr-defined]

    sklearn_preprocessing = ModuleType("sklearn.preprocessing")

    class _StubStandardScaler:
        def fit(self, data, *_args, **_kwargs):
            return self

        def transform(self, data):
            return data

        def fit_transform(self, data, *_args, **_kwargs):
            return data

    sklearn_preprocessing.StandardScaler = _StubStandardScaler  # type: ignore[attr-defined]
    sklearn_module.preprocessing = sklearn_preprocessing  # type: ignore[attr-defined]

    sklearn_impute = ModuleType("sklearn.impute")

    class _StubSimpleImputer:
        def __init__(self, *_, **__):
            pass

        def fit(self, data, *_args, **_kwargs):
            return self

        def transform(self, data):
            return data

        def fit_transform(self, data, *_args, **_kwargs):
            return data

    sklearn_impute.SimpleImputer = _StubSimpleImputer  # type: ignore[attr-defined]
    sklearn_module.impute = sklearn_impute  # type: ignore[attr-defined]

    sklearn_ensemble.HistGradientBoostingRegressor = _StubIsolationForest  # type: ignore[attr-defined]

    return {
        "sklearn": sklearn_module,
        "sklearn.ensemble": sklearn_ensemble,
        "sklearn.cluster": sklearn_cluster,
        "sklearn.pipeline": sklearn_pipeline,
        "sklearn.feature_extraction": sklearn_feature,
        "sklearn.feature_extraction.text": sklearn_feature_text,
        "sklearn.linear_model": sklearn_linear,
        "sklearn.preprocessing": sklearn_preprocessing,
        "sklearn.impute": sklearn_impute,
    }
