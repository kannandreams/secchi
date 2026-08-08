"""Portable JSON, Markdown, and HTML package intelligence reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from secchi.errors import ReportError
from secchi.export import export_package_json
from secchi.models import DerivedPackageData, PackageInfo, PackageRef, Project
from secchi.renderers.summary import render_summary
from secchi.schema import PROJECT_EXPORT_SCHEMA_VERSION
from secchi.schemas import ProjectExport

SECCHI_REPOSITORY_URL = "https://github.com/kannandreams/secchi"


@dataclass
class ProjectSourceReport:
    ref: PackageRef
    info: PackageInfo | None
    derived: DerivedPackageData | None
    error: str | None = None
    warnings: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ProjectReport:
    project: Project
    sources: list[ProjectSourceReport]
    generated_at: datetime


def build_project_report(
    project: Project,
    results: dict[str, object],
) -> ProjectReport:
    """Build a project report from already-fetched intelligence results."""
    from secchi.aggregate import package_key
    from secchi.services.intelligence import IntelligenceResult

    sources: list[ProjectSourceReport] = []
    for ref in project.packages:
        result = results.get(package_key(ref))
        if not isinstance(result, IntelligenceResult):
            sources.append(ProjectSourceReport(ref, None, None, "No result returned."))
            continue
        error = result.error.message if result.error else None
        warnings = [
            {"source": warning.source, "message": warning.message}
            for warning in result.warnings
        ]
        sources.append(
            ProjectSourceReport(ref, result.info, result.derived, error, warnings)
        )
    return ProjectReport(
        project=project,
        sources=sources,
        generated_at=datetime.now(timezone.utc),
    )


def render_report(
    format_name: str,
    info: PackageInfo,
    derived: DerivedPackageData,
    ref: PackageRef,
    project_name: str,
    warnings: list[object] | None = None,
) -> str:
    if format_name == "json":
        return export_package_json(info, derived, ref, project_name, warnings)
    if format_name == "md":
        return render_markdown(info, derived, ref, warnings)
    if format_name == "html":
        return render_html(info, derived, ref, warnings)
    raise ReportError(f"Unsupported report format: {format_name}")


def render_markdown(
    info: PackageInfo,
    derived: DerivedPackageData,
    ref: PackageRef,
    warnings: list[object] | None = None,
) -> str:
    change = derived.downloads_30d_pct_change
    adoption = (
        "No baseline available"
        if change is None
        else f"{change:+.1f}% vs previous 30 days"
    )
    rows = "\n".join(
        f"| {score.label} | {score.score} / {score.max_score} |"
        for score in derived.health_score.sub_scores
    )
    return f"""# {info.name}

Registry: `{ref.registry.value}`

{info.description or "No package description available."}

## Overview

| Signal | Value |
| --- | --- |
| Health score | {derived.health_score.total} / 100 ({derived.health_score.grade}) |
| Latest version | {info.latest_version or "—"} |
| Downloads (30d) | {derived.downloads_30d_total:,} |
| Adoption change | {adoption} |
| GitHub stars | {info.github_stats.stars:,} |
| Reverse dependencies | {info.reverse_dependency_count if info.reverse_dependency_count is not None else "—"} |
| Security advisories | {len(info.security_advisories)} affecting latest version |

{_markdown_advisories(info)}

## Health breakdown

| Category | Score |
| --- | --- |
{rows}

{_markdown_warnings(warnings)}
{_markdown_attribution(info.repository_url)}
"""


def render_html(
    info: PackageInfo,
    derived: DerivedPackageData,
    ref: PackageRef,
    warnings: list[object] | None = None,
) -> str:
    rows = "".join(
        f"<tr><td>{escape(score.label)}</td><td>{score.score} / {score.max_score}</td></tr>"
        for score in derived.health_score.sub_scores
    )
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Secchi report: {escape(info.name)}</title>
<style>body{{font:16px system-ui,sans-serif;max-width:900px;margin:3rem auto;padding:0 1rem;line-height:1.5;color:#18212f}}table{{border-collapse:collapse;width:100%;max-width:720px}}th,td{{border:1px solid #d7dde7;padding:.55rem;text-align:left}}th{{background:#eef2f7}}</style>
</head><body><h1>{escape(info.name)}</h1><p>{escape(info.description or "No package description available.")}</p>
<p>Registry: <code>{escape(ref.registry.value)}</code></p><h2>Overview</h2>
<table><tr><th>Signal</th><th>Value</th></tr>
<tr><td>Health score</td><td>{derived.health_score.total} / 100 ({escape(derived.health_score.grade)})</td></tr>
<tr><td>Latest version</td><td>{escape(info.latest_version or "—")}</td></tr>
<tr><td>Downloads (30d)</td><td>{derived.downloads_30d_total:,}</td></tr>
<tr><td>GitHub stars</td><td>{info.github_stats.stars:,}</td></tr></table>
{_html_advisories(info)}
<h2>Health breakdown</h2><table><tr><th>Category</th><th>Score</th></tr>{rows}</table>
{_html_warnings(warnings)}
{_html_attribution(info.repository_url)}
</body></html>
"""


def render_terminal_report(info: PackageInfo, derived: DerivedPackageData) -> str:
    """Kept for callers that need a report-like terminal representation."""
    return render_summary(info, derived)


def render_project_report(format_name: str, report: ProjectReport) -> str:
    if format_name == "json":
        return ProjectExport.model_validate(
            _project_report_data(report)
        ).model_dump_json(indent=2, by_alias=True)
    if format_name == "md":
        return _project_markdown(report)
    if format_name == "html":
        return _project_html(report)
    raise ReportError(f"Unsupported report format: {format_name}")


def default_report_path(
    subject: str,
    format_name: str,
    *,
    project: bool = False,
    directory: Path | None = None,
) -> Path:
    safe = subject.replace("/", "_").replace(" ", "_")
    suffix = "project" if project else "package"
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    extension = "md" if format_name == "markdown" else format_name
    return (directory or Path.cwd()) / f"secchi-{safe}-{suffix}-{date}.{extension}"


def _project_report_data(report: ProjectReport) -> dict:
    available = [source for source in report.sources if source.info and source.derived]
    health_scores = [
        source.derived.health_score.total for source in available if source.derived
    ]
    downloads = sum(
        source.derived.downloads_30d_total for source in available if source.derived
    )
    return {
        "schema_version": PROJECT_EXPORT_SCHEMA_VERSION,
        "schema": "secchi.project-intelligence",
        "generated_by": "Secchi",
        "project": {
            "name": report.project.name,
            "title": report.project.title or report.project.name,
            "description": report.project.description,
            "favorite": report.project.favorite,
            "repository": report.project.repository_url,
        },
        "generated_at": report.generated_at.isoformat(),
        "summary": {
            "health_score": round(sum(health_scores) / len(health_scores))
            if health_scores
            else None,
            "downloads_30d": downloads,
            "source_count": len(report.sources),
            "healthy_source_count": len(available),
        },
        "sources": [
            {
                "package": source.ref.name,
                "registry": source.ref.registry.value,
                "latest_version": source.info.latest_version if source.info else None,
                "health_score": source.derived.health_score.total
                if source.derived
                else None,
                "downloads_30d": source.derived.downloads_30d_total
                if source.derived
                else None,
                "security_advisories": len(source.info.security_advisories)
                if source.info
                else None,
                "error": source.error,
                "warnings": source.warnings,
            }
            for source in report.sources
        ],
    }


def _project_markdown(report: ProjectReport) -> str:
    data = _project_report_data(report)
    project = data["project"]
    summary = data["summary"]
    rows = "\n".join(_source_markdown_row(source) for source in data["sources"])
    return f"""# {project["title"]}

{project["description"] or "No project description available."}

Repository: {project["repository"] or "—"}

## Project summary

| Signal | Value |
| --- | --- |
| Health score | {summary["health_score"] if summary["health_score"] is not None else "—"} / 100 |
| Downloads (30d) | {summary["downloads_30d"]:,} |
| Healthy sources | {summary["healthy_source_count"]} / {summary["source_count"]} |

## Package sources

| Package | Registry | Latest version | Health | Downloads (30d) | Advisories | Status |
| --- | --- | --- | ---: | ---: | ---: | --- |
{rows}

{_markdown_attribution(project["repository"])}
"""


def _source_markdown_row(source: dict) -> str:
    downloads = (
        f"{source['downloads_30d']:,}" if source["downloads_30d"] is not None else "—"
    )
    return (
        f"| {source['package']} | {source['registry']} | {source['latest_version'] or '—'} | "
        f"{source['health_score'] if source['health_score'] is not None else '—'} | "
        f"{downloads} | {source['security_advisories'] if source['security_advisories'] is not None else '—'} | {_source_status(source)} |"
    )


def _project_html(report: ProjectReport) -> str:
    data = _project_report_data(report)
    project = data["project"]
    summary = data["summary"]
    rows = "".join(
        "<tr>"
        f"<td>{escape(source['package'])}</td>"
        f"<td>{escape(source['registry'])}</td>"
        f"<td>{escape(str(source['latest_version'] or '—'))}</td>"
        f"<td>{escape(str(source['health_score'] if source['health_score'] is not None else '—'))}</td>"
        f"<td>{source['downloads_30d'] if source['downloads_30d'] is not None else '—'}</td>"
        f"<td>{source['security_advisories'] if source['security_advisories'] is not None else '—'}</td>"
        f"<td>{escape(_source_status(source))}</td></tr>"
        for source in data["sources"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Secchi project report: {escape(project["title"])}</title>
<style>body{{font:16px system-ui,sans-serif;max-width:1000px;margin:3rem auto;padding:0 1rem;line-height:1.5;color:#18212f}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #d7dde7;padding:.55rem;text-align:left}}th{{background:#eef2f7}}.summary{{display:flex;gap:2rem}}.metric{{padding:1rem;background:#f5f7fa;border-radius:.4rem}}</style>
</head><body><h1>{escape(project["title"])}</h1><p>{escape(project["description"] or "No project description available.")}</p>
<p>Repository: {escape(project["repository"] or "—")}</p>
<div class="summary"><div class="metric"><strong>Health</strong><br>{summary["health_score"] if summary["health_score"] is not None else "—"} / 100</div><div class="metric"><strong>Downloads (30d)</strong><br>{summary["downloads_30d"]:,}</div><div class="metric"><strong>Healthy sources</strong><br>{summary["healthy_source_count"]} / {summary["source_count"]}</div></div>
<h2>Package sources</h2><table><thead><tr><th>Package</th><th>Registry</th><th>Latest</th><th>Health</th><th>Downloads (30d)</th><th>Advisories</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>
{_html_attribution(project["repository"])}
</body></html>
"""


def _markdown_attribution(repository_url: str | None) -> str:
    star = f" · [⭐ Star the project]({repository_url})" if repository_url else ""
    return f"Generated by [Secchi]({SECCHI_REPOSITORY_URL}){star}"


def _markdown_advisories(info: PackageInfo) -> str:
    if not info.security_advisories:
        return (
            "## Security advisories\n\nNo known advisories affect the latest version.\n"
        )
    rows = []
    for advisory in info.security_advisories:
        fixed = ", ".join(advisory.fixed_versions) or "No fixed version listed"
        rows.append(
            f"- [{advisory.id}]({advisory.url}) — "
            f"{advisory.severity or 'Severity unavailable'}; fixed: {fixed}; "
            f"{advisory.summary or 'No summary available.'}"
        )
    return "## Security advisories\n\n" + "\n".join(rows) + "\n"


def _html_advisories(info: PackageInfo) -> str:
    if not info.security_advisories:
        return "<h2>Security advisories</h2><p>No known advisories affect the latest version.</p>"
    rows = "".join(
        "<tr>"
        f'<td><a href="{escape(advisory.url, quote=True)}">{escape(advisory.id)}</a></td>'
        f"<td>{escape(advisory.severity or '—')}</td>"
        f"<td>{escape(', '.join(advisory.fixed_versions) or '—')}</td>"
        f"<td>{escape(advisory.summary or '—')}</td>"
        "</tr>"
        for advisory in info.security_advisories
    )
    return (
        "<h2>Security advisories</h2>"
        "<table><tr><th>ID</th><th>Severity</th><th>Fixed version</th><th>Summary</th></tr>"
        f"{rows}</table>"
    )


def _source_status(source: dict) -> str:
    if source["error"]:
        return source["error"]
    warnings = source.get("warnings", [])
    return f"{len(warnings)} signal warning(s)" if warnings else "Healthy"


def _markdown_warnings(warnings: list[object] | None) -> str:
    if not warnings:
        return ""
    rows = "\n".join(f"- `{warning.source}`: {warning.message}" for warning in warnings)
    return f"## Signal warnings\n\n{rows}\n"


def _html_warnings(warnings: list[object] | None) -> str:
    if not warnings:
        return ""
    rows = "".join(
        f"<li><code>{escape(warning.source)}</code>: {escape(warning.message)}</li>"
        for warning in warnings
    )
    return f"<h2>Signal warnings</h2><ul>{rows}</ul>"


def _html_attribution(repository_url: str | None) -> str:
    star = (
        f' · <a href="{escape(repository_url, quote=True)}">⭐ Star the project</a>'
        if repository_url
        else ""
    )
    secchi_link = f'<a href="{escape(SECCHI_REPOSITORY_URL, quote=True)}">Secchi</a>'
    return f'<footer style="margin-top:2rem;color:#5f6b7a">Generated by {secchi_link}{star}</footer>'
