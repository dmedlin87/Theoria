import warnings


def pytest_addoption(parser):
    """Register custom options expected by the test configuration."""
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
