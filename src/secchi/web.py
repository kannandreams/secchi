"""Browser dashboard launcher backed by Textual's local web server."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from secchi.workflows.dashboard import DashboardRequest


class TextualServeUnavailable(RuntimeError):
    """Raised when the Textual CLI is not installed or not on PATH."""


@dataclass(frozen=True)
class WebDashboardLaunch:
    """Details for a generated Textual serve launch."""

    command: list[str]


def build_dashboard_command(
    request: DashboardRequest,
    *,
    package: str | None = None,
    registry: str | None = None,
    project_name: str | None = None,
    refresh: bool = False,
    security_refresh: bool = False,
    verbose: bool = False,
    log_file: Path | None = None,
) -> list[str]:
    """Build the dashboard command Textual serve should run."""

    command = [sys.executable, "-m", "secchi", "dashboard"]
    if package:
        command.append(package)
    if registry:
        command.extend(["--registry", registry])
    if request.config_path.exists():
        command.extend(["--config", str(request.config_path)])
    if project_name:
        command.extend(["--project", project_name])
    if refresh:
        command.append("--no-cache")
    elif security_refresh:
        command.append("--security-no-cache")
    if verbose:
        command.append("--verbose")
    if log_file:
        command.extend(["--log-file", str(log_file)])
    return command


def prepare_launch(
    request: DashboardRequest,
    *,
    package: str | None = None,
    registry: str | None = None,
    project_name: str | None = None,
    refresh: bool = False,
    security_refresh: bool = False,
    verbose: bool = False,
    log_file: Path | None = None,
) -> WebDashboardLaunch:
    """Prepare a local Textual serve launch without starting a subprocess."""

    command = build_dashboard_command(
        request,
        package=package,
        registry=registry,
        project_name=project_name,
        refresh=refresh,
        security_refresh=security_refresh,
        verbose=verbose,
        log_file=log_file,
    )
    return WebDashboardLaunch(command=command)


def run_textual_serve(command: list[str], *, port: int = 8000) -> None:
    """Run the dashboard through Textual's local browser server."""

    textual = shutil.which("textual")
    if textual is None:
        raise TextualServeUnavailable(
            "Browser dashboard support requires the Textual CLI. "
            "Run `uv sync` and use `uv run secchi web`, or install Secchi "
            "with a Textual version that provides `textual serve`."
        )
    subprocess.run(
        [
            textual,
            "serve",
            "--title",
            "Secchi",
            "--port",
            str(port),
            "--command",
            shlex.join(command),
        ],
        check=True,
    )
