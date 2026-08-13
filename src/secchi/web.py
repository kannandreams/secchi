"""Browser dashboard launcher backed by textual-web."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tomli_w import dumps as toml_dumps

from secchi.workflows.dashboard import DashboardRequest


class TextualWebUnavailable(RuntimeError):
    """Raised when textual-web is not installed or not on PATH."""


@dataclass(frozen=True)
class WebDashboardLaunch:
    """Details for a generated textual-web launch."""

    command: list[str]
    config_text: str


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
    """Build the dashboard command textual-web should run."""

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


def build_textual_web_config(command: list[str], *, slug: str = "secchi") -> str:
    """Build textual-web TOML for the Secchi dashboard app."""

    return toml_dumps(
        {
            "app": {
                "Secchi": {
                    "command": shlex.join(command),
                    "slug": slug,
                }
            }
        }
    )


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
    slug: str = "secchi",
) -> WebDashboardLaunch:
    """Prepare a textual-web launch without starting a subprocess."""

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
    return WebDashboardLaunch(
        command=command,
        config_text=build_textual_web_config(command, slug=slug),
    )


def run_textual_web(config_text: str) -> None:
    """Run textual-web with a generated temporary config file."""

    textual_web = shutil.which("textual-web")
    if textual_web is None:
        raise TextualWebUnavailable(
            "Browser dashboard support requires textual-web. "
            "Install the external CLI with `pipx install textual-web`."
        )

    with tempfile.TemporaryDirectory(prefix="secchi-web-") as temp_dir:
        config_path = Path(temp_dir) / "secchi-web.toml"
        config_path.write_text(config_text)
        subprocess.run([textual_web, "--config", str(config_path)], check=True)
