"""CLI helper for running TheoEngine code quality checks."""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import click


@dataclass(frozen=True)
class CheckRequest:
    """Represents a single command-line quality check."""

    label: str
    command: Sequence[str]
    optional: bool = False


@dataclass
class CheckOutcome:
    """Result of executing a :class:`CheckRequest`."""

    request: CheckRequest
    returncode: int
    stdout: str
    stderr: str
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and self.error is None

DEFAULT_RUFF_PATHS: tuple[Path, ...] = (Path("mcp_server"),)
DEFAULT_PYTEST_PATHS: tuple[Path, ...] = (Path("tests/mcp_tools"),)
DEFAULT_MYPY_PATHS: tuple[Path, ...] = (Path("mcp_server"),)


def _format_command(command: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _execute(request: CheckRequest) -> CheckOutcome:
    try:
        completed = subprocess.run(
            list(request.command),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        return CheckOutcome(
            request=request,
            returncode=127,
            stdout="",
            stderr="",
            error=str(exc),
        )
    return CheckOutcome(
        request=request,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _build_checks(
    ruff_paths: Iterable[Path],
    pytest_paths: Iterable[Path],
    mypy_paths: Iterable[Path],
    *,
    skip_ruff: bool,
    skip_pytest: bool,
    include_mypy: bool,
    ruff_args: Sequence[str],
    pytest_args: Sequence[str],
    mypy_args: Sequence[str],
    mypy_config: Path | None,
) -> list[CheckRequest]:
    checks: list[CheckRequest] = []

    if not skip_ruff:
        for path in ruff_paths:
            command = ["ruff", "check", str(path), *ruff_args]
            checks.append(CheckRequest(label=f"ruff ({path})", command=command))

    if not skip_pytest:
        command = ["pytest", *[str(path) for path in pytest_paths], *pytest_args]
        checks.append(CheckRequest(label="pytest", command=command))

    if include_mypy:
        command = ["mypy"]
        if mypy_config is not None:
            command.extend(["--config-file", str(mypy_config)])
        command.extend(str(path) for path in mypy_paths)
        command.extend(mypy_args)
        checks.append(
            CheckRequest(
                label="mypy", command=command, optional=True
            )
        )

    return checks


@click.command(name="code-quality")
@click.option(
    "--ruff-path",
    "ruff_paths",
    type=click.Path(path_type=Path),
    multiple=True,
    default=DEFAULT_RUFF_PATHS,
    show_default=True,
    help="Paths to lint with ruff.",
)
@click.option(
    "--pytest-path",
    "pytest_paths",
    type=click.Path(path_type=Path),
    multiple=True,
    default=DEFAULT_PYTEST_PATHS,
    show_default=True,
    help="Targets to execute with pytest.",
)
@click.option(
    "--mypy-path",
    "mypy_paths",
    type=click.Path(path_type=Path),
    multiple=True,
    default=DEFAULT_MYPY_PATHS,
    show_default=True,
    help="Paths to include when running mypy.",
)
@click.option("--skip-ruff", is_flag=True, help="Skip running ruff lint checks.")
@click.option("--skip-pytest", is_flag=True, help="Skip running pytest.")
@click.option(
    "--include-mypy/--skip-mypy",
    default=False,
    help="Include mypy in the analysis (treated as optional by default).",
)
@click.option(
    "--ruff-arg",
    "ruff_args",
    multiple=True,
    help="Additional arguments forwarded to ruff.",
)
@click.option(
    "--pytest-arg",
    "pytest_args",
    multiple=True,
    help="Additional arguments forwarded to pytest (defaults include -q).",
    default=("-q",),
    show_default=True,
)
@click.option(
    "--mypy-arg",
    "mypy_args",
    multiple=True,
    help="Additional arguments forwarded to mypy.",
)
@click.option(
    "--mypy-config",
    type=click.Path(path_type=Path),
    help="Optional path to a mypy configuration file.",
)
@click.option(
    "--strict/--no-strict",
    default=False,
    help="Treat optional checks as required (non-zero exit on failure).",
)
def code_quality(
    ruff_paths: tuple[Path, ...],
    pytest_paths: tuple[Path, ...],
    mypy_paths: tuple[Path, ...],
    skip_ruff: bool,
    skip_pytest: bool,
    include_mypy: bool,
    ruff_args: tuple[str, ...],
    pytest_args: tuple[str, ...],
    mypy_args: tuple[str, ...],
    mypy_config: Path | None,
    strict: bool,
) -> None:
    """Run TheoEngine code quality checks from the command line."""

    checks = _build_checks(
        ruff_paths,
        pytest_paths,
        mypy_paths,
        skip_ruff=skip_ruff,
        skip_pytest=skip_pytest,
        include_mypy=include_mypy,
        ruff_args=ruff_args,
        pytest_args=pytest_args,
        mypy_args=mypy_args,
        mypy_config=mypy_config,
    )

    if not checks:
        click.echo("No checks selected. Enable at least one command to run.")
        return

    outcomes: list[CheckOutcome] = []
    for check in checks:
        click.echo(f"→ Running {check.label}: {_format_command(check.command)}")
        outcome = _execute(check)
        outcomes.append(outcome)
        if outcome.stdout:
            click.echo(outcome.stdout.rstrip())
        if outcome.stderr:
            click.echo(outcome.stderr.rstrip(), err=True)
        if outcome.error is not None:
            click.echo(outcome.error, err=True)

    exit_code = 0
    optional_failures = []

    click.echo("\nSummary:")
    for outcome in outcomes:
        if outcome.succeeded:
            icon = "✅"
        elif outcome.request.optional and not strict:
            icon = "⚠️"
        else:
            icon = "❌"
        click.echo(f"{icon} {outcome.request.label}")
        if not outcome.succeeded:
            if outcome.request.optional and not strict:
                optional_failures.append(outcome)
            else:
                exit_code = 1

    if optional_failures and not strict:
        click.echo(
            "Optional checks failed; re-run with --strict to exit non-zero.",
            err=True,
        )

    if exit_code != 0:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    code_quality()
