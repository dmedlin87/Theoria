import warnings


try:
    import importlib.util

    _HAS_PYTEST_TIMEOUT = importlib.util.find_spec("pytest_timeout") is not None
except ModuleNotFoundError:  # pragma: no cover - importlib is in stdlib
    _HAS_PYTEST_TIMEOUT = False


def pytest_addoption(parser):
    """Register custom options expected by the test configuration."""
    if not _HAS_PYTEST_TIMEOUT:
        parser.addoption(
            "--timeout",
            action="store",
            default=None,
            help=(
                "Ignored. Allows running the test suite without the pytest-timeout "
                "plugin installed."
            ),
        )
        warnings.filterwarnings(
            "ignore",
            message="pytest.PytestConfigWarning: Unknown config option: timeout",
        )
