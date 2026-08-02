"""Defaults for registries with limited package-level time-series APIs."""

from __future__ import annotations

from secchi.api.base import AdapterBase
from secchi.models import (
    Dependency,
    DownloadCounts,
    DownloadTrendPoint,
    ReverseDependency,
    Version,
)


class SparseAdapter(AdapterBase):
    """Honest empty implementations for optional registry capabilities."""

    async def fetch_versions(self, name: str) -> list[Version]:
        return []

    async def fetch_dependencies(self, name: str, version: str) -> list[Dependency]:
        return []

    async def fetch_download_trend(
        self, name: str, days: int = 30
    ) -> list[DownloadTrendPoint]:
        return []

    async def fetch_download_counts(self, name: str) -> DownloadCounts:
        return DownloadCounts()

    async def fetch_release_notes(self, name: str, version: str) -> str:
        return ""

    async def fetch_reverse_dependencies(
        self, name: str, limit: int = 5
    ) -> list[ReverseDependency]:
        return []

    async def fetch_reverse_dependency_count(self, name: str) -> int | None:
        return None

    async def fetch_version_download_breakdown(self, name: str) -> dict[int | str, int]:
        return {}
