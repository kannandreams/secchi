"""Shared fetch, enrichment, caching, and signal-calculation pipeline."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from secchi import derived as derive
from secchi.aggregate import package_key
from secchi.api.base import create_adapter
from secchi.cache import (
    load_package_cache,
    load_security_cache,
    save_package_cache,
    save_security_cache,
)
from secchi.history import append_snapshot, compute_delta, find_baseline, load_snapshots
from secchi.http import HttpClientFactory
from secchi.models import (
    DerivedPackageData,
    DownloadCounts,
    FetchError,
    GitHubStats,
    HistorySnapshot,
    MetricTimelinePoint,
    PackageInfo,
    PackageRef,
)
from secchi.security import fetch_osv_advisories
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
    warnings: list[SignalWarning] = field(default_factory=list)
    error: FetchError | None = None
    fetched_at: datetime | None = None


@dataclass
class ProjectIntelligence:
    """Results for all registry variants in a project."""

    results: dict[str, IntelligenceResult] = field(default_factory=dict)
    refreshed_at: datetime | None = None


@dataclass(frozen=True)
class SignalWarning:
    """A non-fatal failure while enriching an otherwise valid package."""

    source: str
    message: str


class PackageIntelligenceService:
    """The single application pipeline used by show, dashboard, and reports."""

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        clock: Callable[[], datetime] | None = None,
        http_factory: HttpClientFactory | None = None,
    ) -> None:
        self.cache_dir = cache_dir
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.http_factory = http_factory or HttpClientFactory()

    async def fetch_project(
        self,
        refs: list[PackageRef],
        *,
        force_refresh: bool = False,
        force_security_refresh: bool = False,
    ) -> ProjectIntelligence:
        results = await asyncio.gather(
            *(
                self.fetch_package(
                    ref,
                    force_refresh=force_refresh,
                    force_security_refresh=force_security_refresh,
                )
                for ref in refs
            )
        )
        fetched_times = [result.fetched_at for result in results if result.fetched_at]
        return ProjectIntelligence(
            results={package_key(result.ref): result for result in results},
            refreshed_at=min(fetched_times) if fetched_times else None,
        )

    async def fetch_package(
        self,
        ref: PackageRef,
        *,
        force_refresh: bool = False,
        force_security_refresh: bool = False,
    ) -> IntelligenceResult:
        key = package_key(ref)
        try:
            if not force_refresh:
                cached = self._load_cache(key)
                if cached is not None:
                    info, fetched_at = cached
                    security_warnings = await self._refresh_security_if_needed(
                        key,
                        info,
                        force=force_security_refresh,
                    )
                    return IntelligenceResult(
                        ref=ref,
                        info=info,
                        derived=derive.compute_all(info),
                        warnings=security_warnings,
                        fetched_at=fetched_at,
                    )

            async with self.http_factory.create() as client:
                info, warnings = await self._fetch_fresh(ref, client)
                info.security_advisories, security_warning = await self._fetch_security(
                    key, info, client
                )
                if security_warning:
                    warnings.append(security_warning)
            self._apply_history_deltas(key, info)
            derived = derive.compute_all(info)
            fetched_at = self.clock()
            self._save_cache(key, info, fetched_at)
            return IntelligenceResult(
                ref=ref,
                info=info,
                derived=derived,
                warnings=warnings,
                fetched_at=fetched_at,
            )
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as exc:
            return IntelligenceResult(
                ref=ref,
                error=FetchError(
                    package_name=ref.name, registry=ref.registry, message=str(exc)
                ),
            )

    async def _fetch_fresh(
        self, ref: PackageRef, client
    ) -> tuple[PackageInfo, list[SignalWarning]]:
        try:
            adapter = create_adapter(ref.registry, client=client)
        except TypeError:
            # Keeps lightweight adapter test doubles compatible with the factory.
            adapter = create_adapter(ref.registry)
        info = await adapter.fetch_package(ref.name)
        optional: list[tuple[Any, SignalWarning | None]]
        optional = await asyncio.gather(
            self._optional_signal(
                "versions", lambda: adapter.fetch_versions(ref.name), []
            ),
            self._optional_signal(
                "download trend",
                lambda: adapter.fetch_download_trend(ref.name, days=730),
                [],
            ),
            self._optional_signal(
                "download counts",
                lambda: adapter.fetch_download_counts(ref.name),
                DownloadCounts(),
            ),
            self._optional_signal(
                "GitHub extended stats",
                lambda: fetch_github_extended_stats_for_package(
                    info.homepage, info.repository_url, client=client
                ),
                (GitHubStats(), []),
            ),
            self._optional_signal(
                "version download breakdown",
                lambda: adapter.fetch_version_download_breakdown(ref.name),
                {},
            ),
            self._optional_signal(
                "reverse dependencies",
                lambda: adapter.fetch_reverse_dependencies(ref.name),
                [],
            ),
            self._optional_signal(
                "reverse dependency count",
                lambda: adapter.fetch_reverse_dependency_count(ref.name),
                None,
            ),
        )
        values = [item[0] for item in optional]
        warnings = [item[1] for item in optional if item[1] is not None]
        (
            versions,
            trend,
            counts,
            gh_result,
            version_downloads,
            reverse_dependencies,
            reverse_dependency_count,
        ) = values
        info.versions = versions
        info.download_trend = trend
        info.download_counts = counts
        info.github_stats, info.github_issue_events = gh_result
        info.version_downloads_recent = version_downloads
        info.reverse_dependencies = reverse_dependencies
        info.reverse_dependency_count = reverse_dependency_count

        if info.latest_version:
            dependencies, warning = await self._optional_signal(
                "dependencies",
                lambda: adapter.fetch_dependencies(ref.name, info.latest_version),
                [],
            )
            info.dependencies = dependencies
            if warning:
                warnings.append(warning)
            notes, warning = await self._optional_signal(
                "release notes",
                lambda: adapter.fetch_release_notes(ref.name, info.latest_version),
                "",
            )
            if warning:
                warnings.append(warning)
            if not notes and (info.homepage or info.repository_url):
                github_notes, warning = await self._optional_signal(
                    "GitHub release notes",
                    lambda: fetch_release_notes_for_package(
                        info.homepage,
                        info.repository_url,
                        info.latest_version,
                        client=client,
                    ),
                    "",
                )
                notes = github_notes
                if warning:
                    warnings.append(warning)
            info.release_notes = notes
        return info, warnings

    async def _refresh_security_if_needed(
        self,
        key: str,
        info: PackageInfo,
        *,
        force: bool,
    ) -> list[SignalWarning]:
        if not force:
            cached = self._load_security_cache(key, info.latest_version)
            if cached is not None:
                info.security_advisories = cached[0]
                return []

        async with self.http_factory.create() as client:
            advisories, warning = await self._fetch_security(
                key, info, client, fallback=info.security_advisories
            )
        info.security_advisories = advisories
        return [warning] if warning else []

    async def _fetch_security(
        self,
        key: str,
        info: PackageInfo,
        client,
        *,
        fallback: list | None = None,
    ) -> tuple[list, SignalWarning | None]:
        advisories, warning = await self._optional_signal(
            "security advisories",
            lambda: fetch_osv_advisories(info, client=client),
            fallback if fallback is not None else [],
        )
        if warning is None:
            self._save_security_cache(
                key, info.latest_version, advisories, self.clock()
            )
        return advisories, warning

    async def _optional_signal(
        self,
        source: str,
        operation: Callable[[], Awaitable[Any]],
        default: Any,
    ) -> tuple[Any, SignalWarning | None]:
        """Run one enrichment without making the package fetch fail."""
        try:
            return await operation(), None
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as exc:
            return default, SignalWarning(source=source, message=str(exc))

    def _apply_history_deltas(self, key: str, info: PackageInfo) -> None:
        snapshots = load_snapshots(
            key, path=self._history_path() if self.cache_dir is not None else None
        )
        github = info.github_stats
        if github.resolved:
            baseline = find_baseline(snapshots, now=self.clock)
            github.stars_delta_7d = compute_delta(
                github.stars, baseline.stars if baseline else None
            )
            github.open_issues_delta_7d = compute_delta(
                github.open_issues, baseline.open_issues if baseline else None
            )

        health_total = derive.compute_health_score(info).total
        monthly = find_baseline(
            snapshots, min_age_days=28, max_age_days=35, now=self.clock
        )
        if info.reverse_dependency_count is not None:
            info.reverse_dependency_monthly_growth = compute_delta(
                info.reverse_dependency_count,
                monthly.reverse_dependency_count if monthly else None,
            )
        info.health_history = health_history_points(
            snapshots, health_total, now=self.clock
        )
        append_snapshot(
            key,
            HistorySnapshot(
                timestamp=self.clock(),
                stars=github.stars,
                open_issues=github.open_issues,
                health_score=health_total,
                reverse_dependency_count=info.reverse_dependency_count,
            ),
            path=self._history_path() if self.cache_dir is not None else None,
        )

    def _load_cache(self, key: str):
        if self.cache_dir is None:
            return load_package_cache(key)
        return load_package_cache(key, root=self.cache_dir, now=self.clock)

    def _load_security_cache(self, key: str, package_version: str):
        if self.cache_dir is None:
            return load_security_cache(key, package_version, now=self.clock)
        return load_security_cache(
            key, package_version, root=self.cache_dir, now=self.clock
        )

    def _save_cache(self, key: str, info: PackageInfo, fetched_at: datetime) -> None:
        if self.cache_dir is None:
            save_package_cache(key, info, fetched_at)
        else:
            save_package_cache(key, info, fetched_at, root=self.cache_dir)

    def _save_security_cache(
        self,
        key: str,
        package_version: str,
        advisories: list,
        fetched_at: datetime,
    ) -> None:
        if self.cache_dir is None:
            save_security_cache(key, package_version, advisories, fetched_at)
        else:
            save_security_cache(
                key,
                package_version,
                advisories,
                fetched_at,
                root=self.cache_dir,
            )

    def _history_path(self) -> Path:
        assert self.cache_dir is not None
        return self.cache_dir / "history.json"


def health_history_points(
    snapshots: list[HistorySnapshot],
    current_health: int,
    *,
    now: Callable[[], datetime] | None = None,
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
    current_time = (now or (lambda: datetime.now(timezone.utc)))()
    latest_by_month[current_time.strftime("%Y-%m")] = (current_time, current_health)
    return [
        MetricTimelinePoint(label=timestamp.strftime("%b"), value=value)
        for _, (timestamp, value) in sorted(latest_by_month.items())
    ][-12:]
