"""Base protocol and factory for registry API adapters."""

from __future__ import annotations

from typing import Protocol

from secchi.models import (
    Dependency,
    DownloadCounts,
    DownloadTrendPoint,
    PackageInfo,
    Registry,
    ReverseDependency,
    SearchResult,
    Version,
)


class RegistryAdapter(Protocol):
    """Protocol that all registry API adapters must implement.

    The two capability methods at the bottom have real default bodies rather
    than `...`, so a concrete adapter that lacks a given real signal simply
    inherits an honest empty result instead of silently returning None.
    """

    @property
    def registry(self) -> Registry: ...

    async def fetch_package(self, name: str) -> PackageInfo: ...

    async def fetch_versions(self, name: str) -> list[Version]: ...

    async def fetch_dependencies(self, name: str, version: str) -> list[Dependency]: ...

    async def fetch_download_trend(
        self, name: str, days: int = 30
    ) -> list[DownloadTrendPoint]: ...

    async def fetch_download_counts(self, name: str) -> DownloadCounts: ...

    async def fetch_release_notes(self, name: str, version: str) -> str: ...

    async def fetch_reverse_dependencies(
        self, name: str, limit: int = 5
    ) -> list[ReverseDependency]:
        """Packages depending on this one. Default: no reverse-dep API."""
        return []

    async def fetch_reverse_dependency_count(self, name: str) -> int | None:
        """Total projects depending on this package. Default: no API."""
        return None

    async def fetch_version_download_breakdown(
        self, name: str
    ) -> dict[int | str, int]:
        """Per-version download totals keyed by version id. Default: no API."""
        return {}

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Find packages in this registry; adapters may implement richer search."""
        return []


def create_adapter(registry: Registry) -> RegistryAdapter:
    """Factory: return the correct adapter for a given registry."""
    from secchi.api.crates import CratesAdapter
    from secchi.api.npm import NpmAdapter
    from secchi.api.pypi import PyPIAdapter

    adapters = {
        Registry.PYPI: PyPIAdapter,
        Registry.CRATES: CratesAdapter,
        Registry.NPM: NpmAdapter,
    }
    cls = adapters[registry]
    return cls()
