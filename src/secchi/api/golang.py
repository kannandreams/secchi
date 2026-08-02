"""Go Modules adapter using the public Go module proxy."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import httpx

from secchi.api.sparse import SparseAdapter
from secchi.models import PackageInfo, Registry, SearchResult, Version

GO_PROXY = "https://proxy.golang.org"


def _module_path(name: str) -> str:
    return quote(name, safe="/@")


class GoModuleAdapter(SparseAdapter):
    @property
    def registry(self) -> Registry:
        return Registry.GO

    async def fetch_package(self, name: str) -> PackageInfo:
        module = _module_path(name)
        async with self._client_scope() as client:
            response = await client.get(f"{GO_PROXY}/{module}/@latest")
            response.raise_for_status()
            data = response.json()
        version = data.get("Version", "")
        repository = _repository_url(name)
        return PackageInfo(
            name=name,
            registry=Registry.GO,
            description=f"Go module {name}",
            homepage=f"https://pkg.go.dev/{name}",
            repository_url=repository,
            documentation_url=f"https://pkg.go.dev/{name}",
            latest_version=version,
            latest_release_date=_parse_time(data.get("Time")),
            versions=[
                Version(version=version, release_date=_parse_time(data.get("Time")))
            ]
            if version
            else [],
        )

    async def fetch_versions(self, name: str) -> list[Version]:
        module = _module_path(name)
        async with self._client_scope() as client:
            response = await client.get(f"{GO_PROXY}/{module}/@v/list")
            response.raise_for_status()
        versions = [
            Version(version=line) for line in response.text.splitlines() if line
        ]
        return versions[-100:]

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        # Go has no central keyword-search endpoint. A module path is resolved
        # exactly through the proxy; broader discovery belongs to pkg.go.dev.
        try:
            info = await self.fetch_package(query)
        except httpx.HTTPError:
            return []
        return [
            SearchResult(
                name=query,
                registry=Registry.GO,
                version=info.latest_version,
                description=info.description,
                url=info.documentation_url,
                score=1.0,
                exact=True,
            )
        ]


def _repository_url(name: str) -> str:
    parts = name.split("/")
    if len(parts) >= 3 and parts[0] == "github.com":
        return "/".join(parts[:3])
    return ""


def _parse_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
