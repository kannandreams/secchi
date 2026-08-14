import sys
from pathlib import Path

from secchi.models import PackageRef, Project, Registry
from secchi.web import prepare_launch, run_textual_serve
from secchi.workflows.dashboard import DashboardRequest


def test_prepare_launch_builds_dashboard_command_for_direct_package(
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


def test_textual_serve_invokes_local_server(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("secchi.web.shutil.which", lambda name: "/opt/bin/textual")
    monkeypatch.setattr(
        "secchi.web.subprocess.run", lambda command, check: calls.append((command, check))
    )

    run_textual_serve(
        [sys.executable, "-m", "secchi", "dashboard", "duckdb"], port=8001
    )

    assert calls == [
        (
            [
                "/opt/bin/textual",
                "serve",
                "--title",
                "Secchi",
                "--port",
                "8001",
                "--command",
                f"{sys.executable} -m secchi dashboard duckdb",
            ],
            True,
        )
    ]
