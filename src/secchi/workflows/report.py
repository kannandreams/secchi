"""Package and project report workflow."""

from dataclasses import dataclass
from pathlib import Path

from secchi.config import find_config, load_project
from secchi.renderers.reports import (
    build_project_report,
    default_report_path,
    render_project_report,
    render_report,
)
from secchi.services.intelligence import PackageIntelligenceService
from secchi.services.resolver import parse_package_spec
from secchi.workflows.common import WorkflowError, require_package


@dataclass(frozen=True)
class ReportOutput:
    content: str
    format_name: str
    target: Path


async def run(
    *,
    package: str | None = None,
    project_name: str | None = None,
    config: str | None = None,
    registry: str | None = None,
    format_name: str = "json",
    output: str | None = None,
    refresh: bool = False,
) -> ReportOutput:
    normalized_format = "md" if format_name == "markdown" else format_name
    if project_name:
        config_path = find_config(config)
        if not config_path:
            raise WorkflowError("No config found for project report.")
        project = load_project(config_path, project_name)
        intelligence = await PackageIntelligenceService().fetch_project(
            project.packages, force_refresh=refresh
        )
        project_report = build_project_report(project, intelligence.results)
        content = render_project_report(normalized_format, project_report)
        subject = project.title or project.name
        target = Path(output) if output and output != "-" else default_report_path(
            subject, normalized_format, project=True
        )
    else:
        if not package:
            raise WorkflowError("Provide a package name or --project PROJECT for a report.")
        ref = parse_package_spec(package, registry)
        result = await require_package(ref, refresh)
        content = render_report(
            normalized_format,
            result.info,
            result.derived,
            ref,
            ref.name,
            result.warnings,
        )
        target = Path(output) if output and output != "-" else default_report_path(
            ref.name, normalized_format
        )
    return ReportOutput(content, normalized_format, target)
