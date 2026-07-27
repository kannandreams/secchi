"""Base protocol and factory for registry API adapters."""

from __future__ import annotations

from typing import Protocol

from pkgwatch.models import (
    Dependency,
    DownloadCounts,
    DownloadTrendPoint,
    GitHubStats,
    PackageInfo,
    Registry,
    Version,
)


class RegistryAdapter(Protocol):
    """Protocol that all registry API adapters must implement."""

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


def create_adapter(registry: Registry) -> RegistryAdapter:
    """Factory: return the correct adapter for a given registry."""
    from pkgwatch.api.crates import CratesAdapter
    from pkgwatch.api.npm import NpmAdapter
    from pkgwatch.api.pypi import PyPIAdapter

    adapters = {
        Registry.PYPI: PyPIAdapter,
        Registry.CRATES: CratesAdapter,
        Registry.NPM: NpmAdapter,
    }
    cls = adapters[registry]
    return cls()
