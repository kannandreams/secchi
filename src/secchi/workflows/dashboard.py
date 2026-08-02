"""Dashboard project-resolution workflow."""

from dataclasses import dataclass
from pathlib import Path

from secchi.config import find_config, load_project, load_projects
from secchi.models import PackageRef, Project
from secchi.services.resolver import parse_package_spec, resolve_package
from secchi.workflows.common import WorkflowError


@dataclass(frozen=True)
class DashboardRequest:
    project: Project
    config_path: Path
    workspace: list[Project] | None
    refresh: bool


def _workspace_project(config_path: Path) -> Project:
    projects = load_projects(config_path)
    refs: list[PackageRef] = []
    for project in projects:
        refs.extend(
            PackageRef(
                ref.name,
                ref.registry,
                ref.favorite or project.favorite,
                project.name,
            )
            for ref in project.packages
        )
    return Project(
        name="Workspace", description="Configured Secchi workspace", packages=refs
    )


async def run(
    *,
    package: str | None = None,
    registry: str | None = None,
    project_name: str | None = None,
    config: str | None = None,
    refresh: bool = False,
) -> DashboardRequest:
    config_path = find_config(config)
    workspace: list[Project] | None = None
    if package:
        ref = parse_package_spec(package, registry)
        configured = None
        if config_path and registry is None:
            for candidate in load_projects(config_path):
                if candidate.name.lower() == package.lower() or any(
                    item.name.lower() == package.lower() for item in candidate.packages
                ):
                    configured = candidate
                    break
        if configured is not None:
            project = configured
        elif registry is None:
            refs = await resolve_package(package)
            if not refs:
                raise WorkflowError(
                    f"No exact package named '{package}' was found across registries."
                )
            project = Project(name=ref.name, packages=refs)
        else:
            project = Project(name=ref.name, packages=[ref])
        config_path = config_path or (Path.cwd() / "secchi.toml")
    else:
        if not config_path:
            raise WorkflowError(
                "No config found. Use 'secchi dashboard PACKAGE' or create secchi.toml."
            )
        if project_name:
            project = load_project(config_path, project_name)
        else:
            workspace = load_projects(config_path)
            project = _workspace_project(config_path)
    if not project.packages:
        raise WorkflowError("The selected workspace has no packages.")
    return DashboardRequest(
        project, config_path, workspace if not package else None, refresh
    )
