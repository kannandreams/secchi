"""Configuration loader — reads secchi config files and env vars."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from secchi.errors import ConfigError
from secchi.models import PackageRef, Project, Registry


def _toml_type(value: Any) -> str:
    if isinstance(value, list):
        return "an array"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, int | float):
        return "a number"
    return type(value).__name__


def _require_table(value: Any, description: str) -> dict[str, Any]:
    """Raise a readable ConfigError instead of a raw KeyError/TypeError/
    AttributeError when a config section isn't the TOML table shape the
    loader expects (e.g. `packages = ["requests"]` instead of a table
    per package, or `projects` written as an array)."""
    if not isinstance(value, dict):
        raise ConfigError(
            f"{description} must be a TOML table, got {_toml_type(value)}."
        )
    return value


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
    projects = _require_table(data.get("projects", {}), "'projects'")

    if project_name not in projects:
        available = list(projects.keys())
        hint = f" Available projects: {', '.join(available)}" if available else ""
        raise ConfigError(f"Project '{project_name}' not found in {config_path}.{hint}")

    raw = _require_table(projects[project_name], f"Project '{project_name}'")
    project = Project(
        name=project_name,
        title=raw.get("title", project_name),
        description=raw.get("description", ""),
        favorite=bool(raw.get("favorite", False)),
        repository_url=raw.get("repository", raw.get("repository_url", "")),
    )

    packages = raw.get("packages", [])
    if not isinstance(packages, list):
        raise ConfigError(
            f"'packages' in project '{project_name}' must be an array, "
            f"got {_toml_type(packages)}."
        )

    for index, raw_pkg in enumerate(packages):
        pkg = _require_table(raw_pkg, f"packages[{index}] in project '{project_name}'")
        if not isinstance(pkg.get("name"), str) or not pkg["name"]:
            raise ConfigError(
                f"packages[{index}] in project '{project_name}' is missing a "
                "non-empty 'name'."
            )
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
    return list(_require_table(data.get("projects", {}), "'projects'").keys())


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
