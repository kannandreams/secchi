"""Shared fetch, enrichment, caching, and signal-calculation pipeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from secchi import derived as derive
from secchi.aggregate import package_key
from secchi.api.base import create_adapter
from secchi.cache import load_package_cache, save_package_cache
from secchi.history import append_snapshot, compute_delta, find_baseline, load_snapshots
from secchi.models import (
    DerivedPackageData,
    FetchError,
    HistorySnapshot,
    MetricTimelinePoint,
    PackageInfo,
    PackageRef,
)
from secchi.utils import (
    fetch_github_extended_stats_for_package,
    fetch_release_notes_for_package,
)


@dataclass
class IntelligenceResult:
    """Data produced for one configured package reference."""

    ref: PackageRef
    info: PackageInfo | None = None
    derived: DerivedPackageData | None = None
    error: FetchError | None = None
    fetched_at: datetime | None = None


@dataclass
class ProjectIntelligence:
    """Results for all registry variants in a project."""

    results: dict[str, IntelligenceResult] = field(default_factory=dict)
    refreshed_at: datetime | None = None


class PackageIntelligenceService:
    """The single application pipeline used by show, dashboard, and reports."""

    async def fetch_project(
        self, refs: list[PackageRef], *, force_refresh: bool = False
    ) -> ProjectIntelligence:
        results = await asyncio.gather(
            *(self.fetch_package(ref, force_refresh=force_refresh) for ref in refs)
        )
        fetched_times = [result.fetched_at for result in results if result.fetched_at]
        return ProjectIntelligence(
            results={package_key(result.ref): result for result in results},
            refreshed_at=min(fetched_times) if fetched_times else None,
        )

    async def fetch_package(
        self, ref: PackageRef, *, force_refresh: bool = False
    ) -> IntelligenceResult:
        key = package_key(ref)
        try:
            if not force_refresh:
                cached = load_package_cache(key)
                if cached is not None:
                    info, fetched_at = cached
                    return IntelligenceResult(
                        ref=ref,
                        info=info,
                        derived=derive.compute_all(info),
                        fetched_at=fetched_at,
                    )

            info = await self._fetch_fresh(ref)
            self._apply_history_deltas(key, info)
            derived = derive.compute_all(info)
            fetched_at = datetime.now(timezone.utc)
            save_package_cache(key, info, fetched_at)
            return IntelligenceResult(ref=ref, info=info, derived=derived, fetched_at=fetched_at)
        except Exception as exc:
            return IntelligenceResult(
                ref=ref,
                error=FetchError(package_name=ref.name, registry=ref.registry, message=str(exc)),
            )

    async def _fetch_fresh(self, ref: PackageRef) -> PackageInfo:
        adapter = create_adapter(ref.registry)
        info = await adapter.fetch_package(ref.name)
        (
            versions,
            trend,
            counts,
            gh_result,
            version_downloads,
            reverse_dependencies,
            reverse_dependency_count,
        ) = await asyncio.gather(
            adapter.fetch_versions(ref.name),
            adapter.fetch_download_trend(ref.name, days=730),
            adapter.fetch_download_counts(ref.name),
            fetch_github_extended_stats_for_package(info.homepage, info.repository_url),
            adapter.fetch_version_download_breakdown(ref.name),
            adapter.fetch_reverse_dependencies(ref.name),
            adapter.fetch_reverse_dependency_count(ref.name),
        )
        info.versions = versions
        info.download_trend = trend
        info.download_counts = counts
        info.github_stats, info.github_issue_events = gh_result
        info.version_downloads_recent = version_downloads
        info.reverse_dependencies = reverse_dependencies
        info.reverse_dependency_count = reverse_dependency_count

        if info.latest_version:
            info.dependencies = await adapter.fetch_dependencies(ref.name, info.latest_version)
            notes = await adapter.fetch_release_notes(ref.name, info.latest_version)
            if not notes and (info.homepage or info.repository_url):
                notes = await fetch_release_notes_for_package(
                    info.homepage, info.repository_url, info.latest_version
                )
            info.release_notes = notes
        return info

    def _apply_history_deltas(self, key: str, info: PackageInfo) -> None:
        snapshots = load_snapshots(key)
        github = info.github_stats
        if github.resolved:
            baseline = find_baseline(snapshots)
            github.stars_delta_7d = compute_delta(github.stars, baseline.stars if baseline else None)
            github.open_issues_delta_7d = compute_delta(
                github.open_issues, baseline.open_issues if baseline else None
            )

        health_total = derive.compute_health_score(info).total
        monthly = find_baseline(snapshots, min_age_days=28, max_age_days=35)
        if info.reverse_dependency_count is not None:
            info.reverse_dependency_monthly_growth = compute_delta(
                info.reverse_dependency_count,
                monthly.reverse_dependency_count if monthly else None,
            )
        info.health_history = health_history_points(snapshots, health_total)
        append_snapshot(
            key,
            HistorySnapshot(
                timestamp=datetime.now(timezone.utc),
                stars=github.stars,
                open_issues=github.open_issues,
                health_score=health_total,
                reverse_dependency_count=info.reverse_dependency_count,
            ),
        )


def health_history_points(
    snapshots: list[HistorySnapshot], current_health: int
) -> list[MetricTimelinePoint]:
    latest_by_month: dict[str, tuple[datetime, int]] = {}
    for snapshot in snapshots:
        if snapshot.health_score is None:
            continue
        timestamp = snapshot.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        key = timestamp.strftime("%Y-%m")
        current = latest_by_month.get(key)
        if current is None or timestamp > current[0]:
            latest_by_month[key] = (timestamp, snapshot.health_score)
    now = datetime.now(timezone.utc)
    latest_by_month[now.strftime("%Y-%m")] = (now, current_health)
    return [
        MetricTimelinePoint(label=timestamp.strftime("%b"), value=value)
        for _, (timestamp, value) in sorted(latest_by_month.items())
    ][-12:]
