"""Pure aggregation logic for multi-source and multi-project workspaces."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from secchi.models import (
    DownloadTrendPoint,
    InstallBreakdown,
    InstallMethod,
    PackageInfo,
    PackageRef,
    Registry,
)


def logical_package_refs(refs: list[PackageRef]) -> list[PackageRef]:
    """Collapse same-name registry refs for single-project navigation."""
    grouped: dict[str, PackageRef] = {}
    for ref in refs:
        key = ref.name.lower()
        current = grouped.get(key)
        if current is None:
            grouped[key] = replace(ref)
        elif ref.favorite and not current.favorite:
            current.favorite = True
    return list(grouped.values())


def combine_package_infos(ref: PackageRef, infos: list[PackageInfo]) -> PackageInfo:
    """Combine the same logical package across supported registries."""
    if not infos:
        raise ValueError("at least one package info value is required")

    primary = pick_primary_info(infos)
    combined = replace(primary)
    combined.name = ref.name
    combined.source_registries = unique_registries(info.registry for info in infos)
    combined.total_downloads = sum(info.total_downloads for info in infos)
    combined.download_counts = replace(primary.download_counts)
    combined.download_counts.today = sum(info.download_counts.today for info in infos)
    combined.download_counts.week = sum(info.download_counts.week for info in infos)
    combined.download_counts.month = sum(info.download_counts.month for info in infos)
    combined.download_trend = combine_download_trends(infos)

    best_github = next(
        (info.github_stats for info in infos if info.github_stats.resolved), None
    )
    if best_github is not None:
        combined.github_stats = best_github

    crates_info = next(
        (info for info in infos if info.registry is Registry.CRATES), None
    )
    if crates_info is not None:
        combined.reverse_dependencies = crates_info.reverse_dependencies
        combined.reverse_dependency_count = crates_info.reverse_dependency_count
        combined.reverse_dependency_monthly_growth = (
            crates_info.reverse_dependency_monthly_growth
        )

    combined.health_history = primary.health_history
    return combined


def pick_primary_info(infos: list[PackageInfo]) -> PackageInfo:
    """Choose the preferred source for fields that cannot be combined."""
    for registry in (Registry.CRATES, Registry.PYPI, Registry.NPM):
        for info in infos:
            if info.registry is registry and info.latest_version:
                return info
    return infos[0]


def unique_registries(registries: Iterable[Registry]) -> list[Registry]:
    seen: set[Registry] = set()
    out: list[Registry] = []
    for registry in registries:
        if registry not in seen:
            seen.add(registry)
            out.append(registry)
    return out


def combine_download_trends(infos: list[PackageInfo]) -> list[DownloadTrendPoint]:
    """Sum activity for equal periods across package registries."""
    counts: dict[str, int] = {}
    for info in infos:
        for point in info.download_trend:
            counts[point.date] = counts.get(point.date, 0) + point.count
    return [
        DownloadTrendPoint(date=date, count=counts[date]) for date in sorted(counts)
    ]


def combine_install_breakdown(infos: list[PackageInfo]) -> InstallBreakdown:
    """Build ecosystem distribution from each source's best available total."""
    totals: dict[str, int] = {}
    for info in infos:
        label = info.registry.display_name
        count = info.download_counts.month or sum(
            point.count for point in info.download_trend[-30:]
        )
        if count == 0:
            count = info.total_downloads
        totals[label] = totals.get(label, 0) + count

    total = sum(totals.values())
    if total <= 0:
        return InstallBreakdown(
            methods=[],
            caption="No 30-day download data available across ecosystems.",
        )

    methods = [
        InstallMethod(label=label, count=count, percent=count / total * 100)
        for label, count in sorted(
            totals.items(), key=lambda item: item[1], reverse=True
        )
    ]
    return InstallBreakdown(
        methods=methods,
        caption="Combined from registry 30-day download totals.",
    )
