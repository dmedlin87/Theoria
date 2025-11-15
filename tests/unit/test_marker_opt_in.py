from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

pytest_plugins = ("pytester",)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _seed_project_conftest(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        textwrap.dedent(
            f"""
            import sys
            from pathlib import Path

            PROJECT_ROOT = Path(r"{PROJECT_ROOT}")
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))

            from tests.conftest import *  # noqa: F401,F403
            """
        )
    )


@pytest.mark.parametrize(
    "test_body, args, expected_lines",
    [
        (
            textwrap.dedent(
                """
                import pytest

                def test_missing_marker(pgvector_db):
                    assert pgvector_db is not None
                """
            ),
            ("-rs",),
            ["*missing @pytest.mark.pgvector*"],
        ),
        (
            textwrap.dedent(
                """
                import pytest

                @pytest.mark.pgvector
                def test_pgvector_skipped(pgvector_db):
                    assert pgvector_db is not None
                """
            ),
            ("-rs",),
            ["*requires --pgvector opt-in to run @pgvector tests*"],
        ),
    ],
)
def test_pgvector_marker_enforcement(pytester: pytest.Pytester, test_body, args, expected_lines):
    _seed_project_conftest(pytester)
    pytester.makepyfile(test_body)
    result = pytester.runpytest(*args)

    if "missing" in expected_lines[0]:
        assert result.ret != 0
        result.stderr.fnmatch_lines(expected_lines)
    else:
        result.assert_outcomes(skipped=1)
        result.stdout.fnmatch_lines(expected_lines)


def test_pgvector_fixture_runs_with_cli(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        textwrap.dedent(
            f"""
            import contextlib
            import sys
            from types import SimpleNamespace
            from pathlib import Path

            PROJECT_ROOT = Path(r"{PROJECT_ROOT}")
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))

            from tests import conftest as parent_conftest

            # Explicitly assign pytest hooks to ensure they're recognized
            pytest_addoption = parent_conftest.pytest_addoption
            pytest_configure = parent_conftest.pytest_configure
            pytest_collection_modifyitems = parent_conftest.pytest_collection_modifyitems
            pytest_load_initial_conftests = parent_conftest.pytest_load_initial_conftests

            # Import fixtures and other helpers
            from tests.conftest import *  # noqa: F401,F403

            import tests.fixtures.pgvector as pgvector_module

            @contextlib.contextmanager
            def _fake_pgvector_database(*_, **__):
                clone = SimpleNamespace(
                    name="clone",
                    url="postgresql+psycopg://postgres:postgres@localhost:5432/clone",
                )

                def _create_engine(**_kwargs):
                    return SimpleNamespace(dispose=lambda: None)

                database = SimpleNamespace(
                    container=SimpleNamespace(stop=lambda: None),
                    url="postgresql+psycopg://postgres:postgres@localhost:5432/theo",
                    create_engine=_create_engine,
                    clone_database=lambda *args, **kwargs: clone,
                    drop_clone=lambda *args, **kwargs: None,
                )
                yield database

            pgvector_module.provision_pgvector_database = _fake_pgvector_database
            """
        )
    )
    pytester.makepyfile(
        textwrap.dedent(
            """
            import pytest

            @pytest.mark.pgvector
            def test_pgvector_fixture(pgvector_db):
                assert pgvector_db is not None
            """
        )
    )
    result = pytester.runpytest("--pgvector")
    result.assert_outcomes(passed=1)


def test_schema_fixture_requires_cli(pytester: pytest.Pytester) -> None:
    _seed_project_conftest(pytester)
    pytester.makepyfile(
        textwrap.dedent(
            """
            import pytest

            @pytest.mark.schema
            def test_schema_fixture(integration_database_url):
                assert integration_database_url.startswith("sqlite")
            """
        )
    )

    result = pytester.runpytest("-rs")
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*requires --schema opt-in to run @schema tests*"])
