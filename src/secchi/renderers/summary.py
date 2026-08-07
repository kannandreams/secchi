"""Concise terminal rendering for ``secchi show``."""

from __future__ import annotations

from secchi.models import DerivedPackageData, PackageInfo


def render_summary(info: PackageInfo, derived: DerivedPackageData) -> str:
    change = derived.downloads_30d_pct_change
    adoption = (
        "—" if change is None else f"{'▲' if change >= 0 else '▼'} {abs(change):.1f}%"
    )
    stars = (
        _format_count(info.github_stats.stars) if info.github_stats.resolved else "—"
    )
    dependents = _format_count(info.reverse_dependency_count)
    advisories = str(len(info.security_advisories))
    health = derived.health_score.total
    return "\n".join(
        [
            info.name,
            "─" * max(20, len(info.name)),
            f"Health Score      {health} / 100",
            f"Latest Version    {info.latest_version or '—'}",
            f"Downloads         {adoption}",
            f"GitHub Stars      {stars}",
            f"Dependents        {dependents}",
            f"Security Advisories {advisories}",
        ]
    )


def _format_count(value: int | None) -> str:
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)
