import asyncio

import pytest

import secchi.services.intelligence as intelligence
from secchi.models import (
    DownloadCounts,
    DownloadTrendPoint,
    GitHubStats,
    PackageInfo,
    PackageRef,
    Registry,
    Version,
)


class PartialAdapter:
    async def fetch_package(self, name: str) -> PackageInfo:
        return PackageInfo(name=name, registry=Registry.PYPI, latest_version="1.0.0")

    async def fetch_versions(self, name: str) -> list[Version]:
        raise RuntimeError("registry versions endpoint unavailable")

    async def fetch_download_trend(self, name: str, days: int = 30) -> list[DownloadTrendPoint]:
        return [DownloadTrendPoint("2026-08-01", 10)]

    async def fetch_download_counts(self, name: str) -> DownloadCounts:
        return DownloadCounts(month=10)

    async def fetch_version_download_breakdown(self, name: str) -> dict:
        return {}

    async def fetch_reverse_dependencies(self, name: str) -> list:
        return []

    async def fetch_reverse_dependency_count(self, name: str) -> int | None:
        return None

    async def fetch_dependencies(self, name: str, version: str) -> list:
        return []

    async def fetch_release_notes(self, name: str, version: str) -> str:
        return ""


def test_optional_enrichment_failure_keeps_package_usable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(intelligence, "create_adapter", lambda registry: PartialAdapter())
    monkeypatch.setattr(
        intelligence,
        "fetch_github_extended_stats_for_package",
        _github_result,
    )
    monkeypatch.setattr(intelligence, "load_package_cache", lambda key: None)
    monkeypatch.setattr(intelligence, "save_package_cache", lambda key, info, fetched_at: None)
    monkeypatch.setattr(
        intelligence.PackageIntelligenceService,
        "_apply_history_deltas",
        lambda self, key, info: None,
    )

    result = asyncio.run(
        intelligence.PackageIntelligenceService().fetch_package(
            PackageRef("demo", Registry.PYPI), force_refresh=True
        )
    )

    assert result.error is None
    assert result.info is not None
    assert result.derived is not None
    assert result.info.download_counts.month == 10
    assert [(warning.source, warning.message) for warning in result.warnings] == [
        ("versions", "registry versions endpoint unavailable")
    ]


async def _github_result(
    homepage: str, repository: str, client=None
) -> tuple[GitHubStats, list]:
    return GitHubStats(), []
