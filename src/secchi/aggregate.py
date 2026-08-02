"""Pure helpers for presenting one logical package across registries."""

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


def package_key(ref: PackageRef) -> str:
    project = f"{ref.project_name}:" if ref.project_name else ""
    return f"{project}{ref.registry.value}:{ref.name}"


def logical_package_refs(refs: list[PackageRef]) -> list[PackageRef]:
    """Collapse same-named registry variants into one navigable package."""
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
    """Combine compatible activity signals while retaining a primary profile."""
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
    for registry in (Registry.CRATES, Registry.PYPI, Registry.NPM):
        for info in infos:
            if info.registry is registry and info.latest_version:
                return info
    return infos[0]


def unique_registries(registries: Iterable[Registry]) -> list[Registry]:
    seen: set[Registry] = set()
    return [
        registry
        for registry in registries
        if not (registry in seen or seen.add(registry))
    ]


def combine_download_trends(infos: list[PackageInfo]) -> list[DownloadTrendPoint]:
    counts: dict[str, int] = {}
    for info in infos:
        for point in info.download_trend:
            counts[point.date] = counts.get(point.date, 0) + point.count
    return [
        DownloadTrendPoint(date=date, count=counts[date]) for date in sorted(counts)
    ]


def combine_install_breakdown(infos: list[PackageInfo]) -> InstallBreakdown:
    totals: dict[str, int] = {}
    for info in infos:
        label = info.registry.display_name
        count = info.download_counts.month or sum(
            p.count for p in info.download_trend[-30:]
        )
        totals[label] = totals.get(label, 0) + (count or info.total_downloads)
    total = sum(totals.values())
    if total <= 0:
        return InstallBreakdown(
            caption="No 30-day download data available across ecosystems."
        )
    methods = [
        InstallMethod(label=label, count=count, percent=count / total * 100)
        for label, count in sorted(
            totals.items(), key=lambda item: item[1], reverse=True
        )
    ]
    return InstallBreakdown(
        methods=methods, caption="Combined from registry 30-day download totals."
    )
