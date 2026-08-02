"""Configuration loader — reads secchi config files and env vars."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from secchi.errors import ConfigError
from secchi.models import PackageRef, Project, Registry

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore


def _config_locations() -> list[Path]:
    """Return candidate config file paths in priority order."""
    candidates: list[Path] = []
    candidates.append(Path.cwd() / "secchi.toml")
    candidates.append(Path.cwd() / ".secchi.toml")
    if platform := os.environ.get("XDG_CONFIG_HOME", ""):
        candidates.append(Path(platform) / "secchi" / "config.toml")
    else:
        candidates.append(Path.home() / ".config" / "secchi" / "config.toml")
    return candidates


def find_config(explicit: str | None = None) -> Path | None:
    """Locate the config file.

    Priority: explicit path > ./secchi.toml > ./.secchi.toml >
    ~/.config/secchi/config.toml
    """
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return path
        raise ConfigError(f"Config file not found: {explicit}")

    for candidate in _config_locations():
        if candidate.exists():
            return candidate
    return None


def load_project(config_path: Path, project_name: str) -> Project:
    """Load a single project from the config file."""
    try:
        data = tomllib.loads(config_path.read_text())
    except (OSError, ValueError) as exc:
        raise ConfigError(f"Could not read config file: {config_path}") from exc
    projects = data.get("projects", {})

    if project_name not in projects:
        available = list(projects.keys())
        hint = f" Available projects: {', '.join(available)}" if available else ""
        raise ConfigError(f"Project '{project_name}' not found in {config_path}.{hint}")

    raw = projects[project_name]
    project = Project(
        name=project_name,
        title=raw.get("title", project_name),
        description=raw.get("description", ""),
        favorite=bool(raw.get("favorite", False)),
        repository_url=raw.get("repository", raw.get("repository_url", "")),
    )

    for pkg in raw.get("packages", []):
        name = pkg["name"]
        registry_raw = pkg.get("registry", "pypi")
        # Package-level favorites are retained for compatibility with existing
        # configs. New configs should put this navigation preference on the
        # project instead.
        favorite = bool(pkg.get("favorite", raw.get("favorite", False)))
        try:
            registry = Registry(registry_raw)
        except ValueError:
            raise ConfigError(
                f"Unknown registry '{registry_raw}' for package '{name}'. "
                f"Must be one of: {', '.join(r.value for r in Registry)}"
            ) from None
        project.packages.append(
            PackageRef(
                name=name,
                registry=registry,
                favorite=favorite,
                project_name=project_name,
            )
        )

    return project


def list_projects(config_path: Path) -> list[str]:
    """List all project names in the config file."""
    try:
        data = tomllib.loads(config_path.read_text())
    except (OSError, ValueError) as exc:
        raise ConfigError(f"Could not read config file: {config_path}") from exc
    return list(data.get("projects", {}).keys())


def load_projects(config_path: Path) -> list[Project]:
    """Load every project in configuration order for workspace dashboards."""
    return [load_project(config_path, name) for name in list_projects(config_path)]


def get_env_token(var_name: str) -> str | None:
    """Read an auth token from environment variable.

    Supported vars:
    - SECCHI_GITHUB_TOKEN — GitHub API token for release notes
    """
    token = os.environ.get(var_name)
    return token or None
