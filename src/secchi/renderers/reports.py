"""Portable JSON, Markdown, and HTML package intelligence reports."""

from __future__ import annotations

from html import escape

from secchi.export import export_package_json
from secchi.models import DerivedPackageData, PackageInfo, PackageRef
from secchi.renderers.summary import render_summary


def render_report(
    format_name: str,
    info: PackageInfo,
    derived: DerivedPackageData,
    ref: PackageRef,
    project_name: str,
) -> str:
    if format_name == "json":
        return export_package_json(info, derived, ref, project_name)
    if format_name == "md":
        return render_markdown(info, derived, ref)
    if format_name == "html":
        return render_html(info, derived, ref)
    raise ValueError(f"Unsupported report format: {format_name}")


def render_markdown(info: PackageInfo, derived: DerivedPackageData, ref: PackageRef) -> str:
    change = derived.downloads_30d_pct_change
    adoption = "No baseline available" if change is None else f"{change:+.1f}% vs previous 30 days"
    rows = "\n".join(
        f"| {score.label} | {score.score} / {score.max_score} |"
        for score in derived.health_score.sub_scores
    )
    return f"""# {info.name}

Registry: `{ref.registry.value}`

{info.description or 'No package description available.'}

## Overview

| Signal | Value |
| --- | --- |
| Health score | {derived.health_score.total} / 100 ({derived.health_score.grade}) |
| Latest version | {info.latest_version or '—'} |
| Downloads (30d) | {derived.downloads_30d_total:,} |
| Adoption change | {adoption} |
| GitHub stars | {info.github_stats.stars:,} |
| Reverse dependencies | {info.reverse_dependency_count if info.reverse_dependency_count is not None else '—'} |

## Health breakdown

| Category | Score |
| --- | --- |
{rows}
"""


def render_html(info: PackageInfo, derived: DerivedPackageData, ref: PackageRef) -> str:
    markdown = render_markdown(info, derived, ref)
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Secchi report: {escape(info.name)}</title>
<style>body{{font:16px system-ui,sans-serif;max-width:900px;margin:3rem auto;padding:0 1rem;line-height:1.5}}pre{{white-space:pre-wrap}} </style>
</head><body><pre>{escape(markdown)}</pre></body></html>
"""


def render_terminal_report(info: PackageInfo, derived: DerivedPackageData) -> str:
    """Kept for callers that need a report-like terminal representation."""
    return render_summary(info, derived)
