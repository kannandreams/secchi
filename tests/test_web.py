import sys
from pathlib import Path

from secchi.models import PackageRef, Project, Registry
from secchi.web import build_textual_web_config, prepare_launch
from secchi.workflows.dashboard import DashboardRequest


def test_prepare_launch_builds_textual_web_config_for_direct_package(
    tmp_path: Path,
) -> None:
    request = DashboardRequest(
        project=Project("duckdb", packages=[PackageRef("duckdb", Registry.PYPI)]),
        config_path=tmp_path / "missing-secchi.toml",
        workspace=None,
        refresh=False,
        security_refresh=False,
    )

    launch = prepare_launch(
        request,
        package="duckdb",
        registry="pypi",
        refresh=True,
        slug="secchi-demo",
    )

    assert launch.command == [
        sys.executable,
        "-m",
        "secchi",
        "dashboard",
        "duckdb",
        "--registry",
        "pypi",
        "--no-cache",
    ]
    assert "[app.Secchi]" in launch.config_text
    assert 'slug = "secchi-demo"' in launch.config_text
    assert "--no-cache" in launch.config_text


def test_prepare_launch_preserves_existing_config_and_project(tmp_path: Path) -> None:
    config = tmp_path / "secchi.toml"
    config.write_text("[projects.demo]\npackages = []\n")
    request = DashboardRequest(
        project=Project("demo", packages=[PackageRef("duckdb", Registry.PYPI)]),
        config_path=config,
        workspace=None,
        refresh=False,
        security_refresh=True,
    )

    launch = prepare_launch(
        request,
        project_name="demo",
        security_refresh=True,
        verbose=True,
        log_file=tmp_path / "secchi.log",
    )

    assert "--config" in launch.command
    assert str(config) in launch.command
    assert "--project" in launch.command
    assert "demo" in launch.command
    assert "--security-no-cache" in launch.command
    assert "--verbose" in launch.command
    assert "--log-file" in launch.command


def test_build_textual_web_config_quotes_command_arguments() -> None:
    config = build_textual_web_config(
        [sys.executable, "-m", "secchi", "dashboard", "name with spaces"]
    )

    assert "[app.Secchi]" in config
    assert "'name with spaces'" in config
