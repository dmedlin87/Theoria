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

                def test_missing_marker(pgvector_container):
                    assert pgvector_container is not None
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
                def test_pgvector_skipped(pgvector_container):
                    assert pgvector_container is not None
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
            """
            import sys
            import types
            from pathlib import Path

            PROJECT_ROOT = Path(r"{PROJECT_ROOT}")
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))

            from tests.conftest import *  # noqa: F401,F403

            class _DummyContainer:
                def __init__(self, *_, **__):
                    self._stopped = False

                def with_env(self, *_args, **_kwargs):
                    return self

                def start(self):
                    return None

                def stop(self):
                    self._stopped = True

                def get_connection_url(self):
                    return "postgresql://postgres:postgres@localhost:5432/theo"

            testcontainers = types.ModuleType("testcontainers")
            postgres_module = types.ModuleType("testcontainers.postgres")
            postgres_module.PostgresContainer = _DummyContainer

            sys.modules.setdefault("testcontainers", testcontainers)
            sys.modules.setdefault("testcontainers.postgres", postgres_module)
            """
        )
    )
    pytester.makepyfile(
        textwrap.dedent(
            """
            import pytest

            @pytest.mark.pgvector
            def test_pgvector_fixture(pgvector_container):
                assert pgvector_container is not None
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
