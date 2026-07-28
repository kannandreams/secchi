"""Configuration loader — reads secchi config files and env vars."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from secchi.models import PackageRef, Project, Registry

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore


def _config_locations() -> list[Path]:
    """Return candidate config file paths in priority order."""
    candidates: list[Path] = []
    candidates.append(Path.cwd() / "secchi.toml")
    candidates.append(Path.cwd() / "pkgwatch.toml")
    if platform := os.environ.get("XDG_CONFIG_HOME", ""):
        candidates.append(Path(platform) / "secchi" / "config.toml")
    else:
        candidates.append(Path.home() / ".config" / "secchi" / "config.toml")
    return candidates


def find_config(explicit: str | None = None) -> Path | None:
    """Locate the config file.

    Priority: explicit path > ./secchi.toml > ./pkgwatch.toml >
    ~/.config/secchi/config.toml
    """
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(f"Config file not found: {explicit}")

    for candidate in _config_locations():
        if candidate.exists():
            return candidate
    return None


def load_project(config_path: Path, project_name: str) -> Project:
    """Load a single project from the config file."""
    data = tomllib.loads(config_path.read_text())
    projects = data.get("projects", {})

    if project_name not in projects:
        available = list(projects.keys())
        if available:
            hint = f" Available projects: {', '.join(available)}"
        else:
            hint = ""
        raise ValueError(
            f"Project '{project_name}' not found in {config_path}.{hint}"
        )

    raw = projects[project_name]
    project = Project(
        name=project_name,
        description=raw.get("description", ""),
    )

    for pkg in raw.get("packages", []):
        name = pkg["name"]
        registry_raw = pkg.get("registry", "pypi")
        favorite = bool(pkg.get("favorite", False))
        try:
            registry = Registry(registry_raw)
        except ValueError:
            raise ValueError(
                f"Unknown registry '{registry_raw}' for package '{name}'. "
                f"Must be one of: {', '.join(r.value for r in Registry)}"
            )
        project.packages.append(
            PackageRef(name=name, registry=registry, favorite=favorite)
        )

    return project


def list_projects(config_path: Path) -> list[str]:
    """List all project names in the config file."""
    data = tomllib.loads(config_path.read_text())
    return list(data.get("projects", {}).keys())


def get_env_token(var_name: str) -> str | None:
    """Read an auth token from environment variable.

    Supported vars:
    - SECCHI_GITHUB_TOKEN — GitHub API token for release notes
    - PKGWATCH_GITHUB_TOKEN — legacy fallback for SECCHI_GITHUB_TOKEN
    """
    token = os.environ.get(var_name)
    if token:
        return token
    if var_name == "SECCHI_GITHUB_TOKEN":
        return os.environ.get("PKGWATCH_GITHUB_TOKEN")
    return None
