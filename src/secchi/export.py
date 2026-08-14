"""Report file helpers for package and project exports."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from secchi.models import (
    DerivedPackageData,
    PackageInfo,
    PackageRef,
)
from secchi.schemas import PackageExport, SignalWarningSchema


def export_package_json(
    info: PackageInfo,
    derived: DerivedPackageData | None,
    ref: PackageRef,
    project_name: str,
    warnings: list[object] | None = None,
) -> str:
    document = PackageExport(
        project=project_name,
        package=ref.name,
        registry=ref.registry.value,
        exported_at=datetime.now(UTC),
        package_info=_serialize_package_info(info) if info else None,
        derived=_serialize_derived(derived) if derived else None,
        warnings=[
            SignalWarningSchema(source=warning.source, message=warning.message)
            for warning in (warnings or [])
        ],
    )
    return document.model_dump_json(indent=2, by_alias=True)


def save_export(json_str: str, project_name: str, pkg_name: str) -> Path:
    return save_report(json_str, project_name, pkg_name, "json")


def save_report(
    content: str,
    project_name: str,
    subject: str,
    format_name: str,
    directory: Path | None = None,
) -> Path:
    """Save a report in the target directory, creating it when necessary."""
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = report_filename(project_name, subject, format_name, date=date)
    path = (directory or Path.cwd()) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def report_filename(
    project_name: str,
    subject: str,
    format_name: str,
    *,
    date: str | None = None,
) -> str:
    """Return the stable filename used for terminal and browser exports."""

    safe_project = project_name.replace("/", "_").replace(" ", "_")
    safe_subject = subject.replace("/", "_").replace(" ", "_")
    extension = "md" if format_name == "markdown" else format_name
    export_date = date or datetime.now(UTC).strftime("%Y-%m-%d")
    return f"secchi-{safe_project}-{safe_subject}-{export_date}.{extension}"


def report_mime_type(format_name: str) -> str:
    """Return the MIME type for a supported report format."""

    return {
        "markdown": "text/markdown",
        "md": "text/markdown",
        "json": "application/json",
        "html": "text/html",
    }.get(format_name, "application/octet-stream")


def _serialize_package_info(info: PackageInfo) -> dict[str, Any]:
    return {
        "name": info.name,
        "registry": info.registry.value,
        "source_registries": [r.value for r in info.source_registries],
        "description": info.description,
        "author": info.author,
        "license": info.license,
        "homepage": info.homepage,
        "repository_url": info.repository_url,
        "documentation_url": info.documentation_url,
        "latest_version": info.latest_version,
        "latest_release_date": info.latest_release_date.isoformat()
        if info.latest_release_date
        else None,
        "total_downloads": info.total_downloads,
        "download_counts": {
            "today": info.download_counts.today,
            "week": info.download_counts.week,
            "month": info.download_counts.month,
        },
        "github_stats": {
            "stars": info.github_stats.stars,
            "forks": info.github_stats.forks,
            "open_issues": info.github_stats.open_issues,
            "has_ci": info.github_stats.has_ci,
            "has_readme": info.github_stats.has_readme,
            "stars_delta_7d": info.github_stats.stars_delta_7d,
            "open_issues_delta_7d": info.github_stats.open_issues_delta_7d,
            "created_at": info.github_stats.created_at.isoformat()
            if info.github_stats.created_at
            else None,
            "pushed_at": info.github_stats.pushed_at.isoformat()
            if info.github_stats.pushed_at
            else None,
        },
        "versions": [
            {
                "version": v.version,
                "release_date": v.release_date.isoformat() if v.release_date else None,
                "downloads": v.downloads,
                "is_yanked": v.is_yanked,
                "size_bytes": v.size_bytes,
            }
            for v in info.versions
        ],
        "dependencies": [
            {
                "name": d.name,
                "requirement": d.requirement,
                "optional": d.optional,
            }
            for d in info.dependencies
        ],
        "download_trend": [
            {"date": p.date, "count": p.count} for p in info.download_trend
        ],
        "reverse_dependency_count": info.reverse_dependency_count,
        "reverse_dependency_monthly_growth": info.reverse_dependency_monthly_growth,
        "health_history": [
            {"label": p.label, "value": p.value} for p in info.health_history
        ],
        "security_advisories": [
            {
                "id": advisory.id,
                "summary": advisory.summary,
                "details": advisory.details,
                "aliases": advisory.aliases,
                "severity": advisory.severity,
                "published": advisory.published.isoformat()
                if advisory.published
                else None,
                "modified": advisory.modified.isoformat()
                if advisory.modified
                else None,
                "fixed_versions": advisory.fixed_versions,
                "references": [
                    {"type": reference.type, "url": reference.url}
                    for reference in advisory.references
                ],
                "url": advisory.url,
            }
            for advisory in info.security_advisories
        ],
    }


def _serialize_derived(derived: DerivedPackageData) -> dict[str, Any]:
    return {
        "health_score": {
            "total": derived.health_score.total,
            "grade": derived.health_score.grade,
            "sub_scores": [
                {"label": s.label, "score": s.score, "max_score": s.max_score}
                for s in derived.health_score.sub_scores
            ],
        },
        "downloads_30d": {
            "total": derived.downloads_30d_total,
            "pct_change": derived.downloads_30d_pct_change,
        },
        "install_breakdown": [
            {"label": m.label, "count": m.count, "percent": m.percent}
            for m in derived.install_breakdown.methods
        ],
        "reverse_dependencies": {
            "count": derived.reverse_dependency_summary.count,
            "monthly_growth": derived.reverse_dependency_summary.monthly_growth,
        },
        "health_timeline": [
            {"label": p.label, "value": p.value} for p in derived.health_timeline
        ],
        "activity": [
            {
                "kind": ev.kind.value,
                "timestamp": ev.timestamp.isoformat(),
                "title": ev.title,
                "ref": ev.ref,
                "url": ev.url,
            }
            for ev in derived.activity
        ],
        "release_adoption": derived.release_adoption,
    }


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
