"""Base protocol and factory for registry API adapters."""

from __future__ import annotations

from typing import ClassVar, Protocol

import httpx

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

    async def fetch_version_download_breakdown(self, name: str) -> dict[int | str, int]:
        """Per-version download totals keyed by version id. Default: no API."""
        return {}

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Find packages in this registry; adapters may implement richer search."""
        return []


class AdapterBase:
    """Shared client binding for concrete registry adapters."""

    default_headers: ClassVar[dict[str, str]] = {}

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    def _client_scope(self):
        return _ClientLease(self.client, self.default_headers)


class _ClientLease:
    """Context-manager view that never closes the shared client."""

    def __init__(
        self, client: httpx.AsyncClient, headers: dict[str, str] | None = None
    ) -> None:
        self.client = client
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    @property
    def diagnostics(self):
        return getattr(self.client, "diagnostics", None)

    async def get(self, url: str, *args, **kwargs):
        headers = httpx.Headers(self.client.headers)
        headers.update(self.headers)
        headers.update(kwargs.pop("headers", {}) or {})
        return await self.client.get(url, *args, headers=headers, **kwargs)


def create_adapter(registry: Registry, *, client: httpx.AsyncClient) -> RegistryAdapter:
    """Factory: return the correct adapter for a given registry."""
    from secchi.api.cran import CranAdapter
    from secchi.api.crates import CratesAdapter
    from secchi.api.golang import GoModuleAdapter
    from secchi.api.homebrew import HomebrewAdapter
    from secchi.api.npm import NpmAdapter
    from secchi.api.pubdev import PubDevAdapter
    from secchi.api.pypi import PyPIAdapter

    adapters = {
        Registry.PYPI: PyPIAdapter,
        Registry.CRATES: CratesAdapter,
        Registry.NPM: NpmAdapter,
        Registry.HOMEBREW: HomebrewAdapter,
        Registry.GO: GoModuleAdapter,
        Registry.CRAN: CranAdapter,
        Registry.PUB: PubDevAdapter,
    }
    cls = adapters[registry]
    return cls(client)
