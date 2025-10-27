"""Shared test configuration for API-level tests."""
from __future__ import annotations

import os
import shutil
import sys
import types

os.environ.setdefault("SETTINGS_SECRET_KEY", "test-secret-key")
os.environ.setdefault("THEO_API_KEYS", '["pytest-default-key"]')
os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("THEORIA_ENVIRONMENT", "development")
os.environ.setdefault("THEO_FORCE_EMBEDDING_FALLBACK", "1")


class _StubFlagModel:
    """Lightweight embedding stub used during API tests."""

    def __init__(self, *_, **__):
        self._dimension = 1024

    def encode(self, texts):
        vectors = []
        for index, _ in enumerate(texts):
            base = float((index % 100) + 1)
            vectors.append(
                [((base + offset) % 100) / 100.0 for offset in range(self._dimension)]
            )
        return vectors


flag_module = types.ModuleType("FlagEmbedding")
flag_module.FlagModel = _StubFlagModel  # type: ignore[attr-defined]
sys.modules.setdefault("FlagEmbedding", flag_module)


def _register_sklearn_stubs() -> None:
    """Provide lightweight sklearn replacements for test environments."""

    if "sklearn" in sys.modules:
        return

    sklearn_module = types.ModuleType("sklearn")

    sklearn_ensemble = types.ModuleType("sklearn.ensemble")

    class _StubIsolationForest:
        def __init__(self, *_, **__):
            self._scores: list[float] | None = None

        def fit(self, embeddings):
            count = len(embeddings) if embeddings is not None else 0
            self._scores = [-0.1 for _ in range(count)]
            return self

        def decision_function(self, embeddings):
            scores = self._scores or [-0.1 for _ in range(len(embeddings) or 0)]
            return scores

        def predict(self, embeddings):
            return [-1 for _ in range(len(embeddings) or 0)]

    sklearn_ensemble.IsolationForest = _StubIsolationForest  # type: ignore[attr-defined]
    sklearn_module.ensemble = sklearn_ensemble  # type: ignore[attr-defined]

    sklearn_cluster = types.ModuleType("sklearn.cluster")

    class _StubDBSCAN:
        def __init__(self, *_, **__):
            pass

        def fit_predict(self, points):
            return [0 for _ in range(len(points) or 0)]

    sklearn_cluster.DBSCAN = _StubDBSCAN  # type: ignore[attr-defined]
    sklearn_module.cluster = sklearn_cluster  # type: ignore[attr-defined]

    sklearn_pipeline = types.ModuleType("sklearn.pipeline")

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

    sklearn_feature = types.ModuleType("sklearn.feature_extraction")
    sklearn_feature_text = types.ModuleType("sklearn.feature_extraction.text")

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

    sklearn_linear = types.ModuleType("sklearn.linear_model")

    class _StubLogisticRegression:
        def __init__(self, *_, **__):
            pass

        def fit(self, *_args, **_kwargs):
            return self

        def predict(self, data):
            return [0 for _ in range(len(data) or 0)]

    sklearn_linear.LogisticRegression = _StubLogisticRegression  # type: ignore[attr-defined]
    sklearn_module.linear_model = sklearn_linear  # type: ignore[attr-defined]

    sklearn_preprocessing = types.ModuleType("sklearn.preprocessing")

    class _StubStandardScaler:
        def fit(self, data, *_args, **_kwargs):
            return self

        def transform(self, data):
            return data

        def fit_transform(self, data, *_args, **_kwargs):
            return data

    sklearn_preprocessing.StandardScaler = _StubStandardScaler  # type: ignore[attr-defined]
    sklearn_module.preprocessing = sklearn_preprocessing  # type: ignore[attr-defined]

    sklearn_impute = types.ModuleType("sklearn.impute")

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

    sys.modules.setdefault("sklearn", sklearn_module)
    sys.modules.setdefault("sklearn.ensemble", sklearn_ensemble)
    sys.modules.setdefault("sklearn.cluster", sklearn_cluster)
    sys.modules.setdefault("sklearn.pipeline", sklearn_pipeline)
    sys.modules.setdefault("sklearn.feature_extraction", sklearn_feature)
    sys.modules.setdefault("sklearn.feature_extraction.text", sklearn_feature_text)
    sys.modules.setdefault("sklearn.linear_model", sklearn_linear)
    sys.modules.setdefault("sklearn.preprocessing", sklearn_preprocessing)
    sys.modules.setdefault("sklearn.impute", sklearn_impute)


_register_sklearn_stubs()

from pathlib import Path

import pytest

pytestmark = pytest.mark.schema
from fastapi import Request as FastAPIRequest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.infrastructure.api.app.main import app
from theo.infrastructure.api.app.db import run_sql_migrations as migrations_module
from theo.application.facades import database as database_module
from theo.application.facades.database import Base, configure_engine, get_engine
from theo.infrastructure.api.app.adapters.security import require_principal

@pytest.fixture(autouse=True)
def _bypass_authentication(request: pytest.FixtureRequest):
    """Permit unauthenticated access for API tests unless explicitly disabled."""

    if request.node.get_closest_marker("no_auth_override"):
        yield
        return

    def _principal_override(fastapi_request: FastAPIRequest):
        principal = {"method": "override", "subject": "test"}
        fastapi_request.state.principal = principal
        return principal

    app.dependency_overrides[require_principal] = _principal_override
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_principal, None)


@pytest.fixture(autouse=True)
def _disable_migrations(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prevent migrations from running during API startup.

    Migrations are already applied by the integration_database_url fixture,
    so we don't need to run them again during FastAPI app lifespan startup.
    """

    if request.node.get_closest_marker("schema"):
        yield
        return

    # Replace run_sql_migrations with a no-op since migrations were already
    # applied by the fixture that created the test database
    def _noop_run_sql_migrations(
        engine=None,
        migrations_path=None,
        *,
        force: bool = False,
    ) -> list[str]:
        return []

    monkeypatch.setattr(
        migrations_module,
        "run_sql_migrations",
        _noop_run_sql_migrations,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.bootstrap.lifecycle.run_sql_migrations",
        _noop_run_sql_migrations,
    )

    yield


@pytest.fixture(scope="session", autouse=True)
def _skip_heavy_startup() -> None:
    monkeypatch = pytest.MonkeyPatch()
    """Disable expensive FastAPI lifespan setup steps for API tests."""

    from sqlalchemy import text as _sql_text
    from theo.infrastructure.api.app.db import seeds as _seeds_module

    original_seed_reference_data = _seeds_module.seed_reference_data

    def _maybe_seed_reference_data(session) -> None:
        """Invoke the real seeders when the database still needs backfilling."""

        needs_seeding = True
        try:
            bind = session.get_bind()
            if bind is not None:
                try:
                    perspective_present = bool(
                        session.execute(
                            _sql_text(
                                "SELECT 1 FROM pragma_table_info('contradiction_seeds') "
                                "WHERE name = 'perspective'"
                            )
                        ).first()
                    )
                except Exception:
                    perspective_present = False
                if perspective_present:
                    try:
                        has_rows = bool(
                            session.execute(
                                _sql_text(
                                    "SELECT 1 FROM contradiction_seeds LIMIT 1"
                                )
                            ).first()
                        )
                    except Exception:
                        has_rows = False
                    needs_seeding = not has_rows
                else:
                    needs_seeding = True
        except Exception:
            needs_seeding = True

        if needs_seeding:
            original_seed_reference_data(session)

    monkeypatch.setattr(
        "theo.infrastructure.api.app.bootstrap.lifecycle.seed_reference_data",
        _maybe_seed_reference_data,
        raising=False,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.bootstrap.lifecycle.start_discovery_scheduler",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.bootstrap.lifecycle.stop_discovery_scheduler",
        lambda: None,
        raising=False,
    )

    try:
        yield
    finally:
        monkeypatch.undo()


@pytest.fixture(scope="session")
def _api_engine_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Materialise a migrated SQLite database once per test session."""
    from theo.infrastructure.api.app.db.run_sql_migrations import run_sql_migrations

    template_dir = tmp_path_factory.mktemp("api-engine-template")
    template_path = template_dir / "api.sqlite"
    engine = create_engine(f"sqlite:///{template_path}", future=True)
    try:
        Base.metadata.create_all(bind=engine)
        run_sql_migrations(engine)
    finally:
        engine.dispose()
    return template_path


@pytest.fixture()
def api_engine(
    tmp_path_factory: pytest.TempPathFactory,
    _api_engine_template: Path,
):
    """Provide an isolated SQLite engine for API tests with pre-applied migrations."""
    database_path = tmp_path_factory.mktemp("db") / "api.sqlite"
    # Clone the pre-migrated template so each test starts from the same baseline.
    shutil.copy2(_api_engine_template, database_path)
    configure_engine(f"sqlite:///{database_path}")

    engine = get_engine()

    try:
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


@pytest.fixture()
def api_test_client(api_engine) -> TestClient:
    """Yield a ``TestClient`` bound to an isolated, migrated database."""

    with TestClient(app) as client:
        yield client

