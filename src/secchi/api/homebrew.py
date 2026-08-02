"""Homebrew formula adapter using the public formulae API."""

from __future__ import annotations

import httpx

from secchi.api.sparse import SparseAdapter
from secchi.models import PackageInfo, Registry, SearchResult, Version

FORMULA_API = "https://formulae.brew.sh/api/formula"


class HomebrewAdapter(SparseAdapter):
    @property
    def registry(self) -> Registry:
        return Registry.HOMEBREW

    async def fetch_package(self, name: str) -> PackageInfo:
        async with self._client_scope() as client:
            response = await client.get(f"{FORMULA_API}/{name}.json")
            response.raise_for_status()
            data = response.json()
        stable = data.get("versions", {}).get("stable", "")
        homepage = data.get("homepage", "")
        formula_url = f"https://formulae.brew.sh/formula/{name}"
        return PackageInfo(
            name=data.get("name", name),
            registry=Registry.HOMEBREW,
            description=data.get("desc", ""),
            homepage=homepage,
            repository_url=homepage,
            latest_version=stable,
            license=data.get("license", "") or "",
            versions=[Version(version=stable)] if stable else [],
            package_kind="Library",
            documentation_url=formula_url,
        )

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        async with self._client_scope() as client:
            try:
                response = await client.get(f"{FORMULA_API}/{query}.json")
                response.raise_for_status()
            except httpx.HTTPError:
                return []
            data = response.json()
        name = data.get("name", query)
        return [
            SearchResult(
                name=name,
                registry=Registry.HOMEBREW,
                version=data.get("versions", {}).get("stable", ""),
                description=data.get("desc", ""),
                url=f"https://formulae.brew.sh/formula/{name}",
                score=1.0,
                exact=name.casefold() == query.casefold(),
            )
        ]
