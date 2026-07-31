"""CRAN adapter for R packages."""

from __future__ import annotations

import httpx

from secchi.api.sparse import SparseAdapter
from secchi.models import Dependency, PackageInfo, Registry, SearchResult, Version


CRAN_DB = "https://crandb.r-pkg.org"


class CranAdapter(SparseAdapter):
    @property
    def registry(self) -> Registry:
        return Registry.CRAN

    async def fetch_package(self, name: str) -> PackageInfo:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{CRAN_DB}/{name}")
            response.raise_for_status()
            data = response.json()
        homepage = _first_url(data.get("URL", ""))
        return PackageInfo(
            name=data.get("Package", name),
            registry=Registry.CRAN,
            description=data.get("Title", ""),
            author=data.get("Maintainer", ""),
            license=data.get("License", ""),
            homepage=homepage,
            repository_url=homepage,
            latest_version=data.get("Version", ""),
            documentation_url=f"https://cran.r-project.org/package={name}",
            versions=[Version(version=data.get("Version", ""))]
            if data.get("Version")
            else [],
            dependencies=_dependencies(data),
        )

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        try:
            info = await self.fetch_package(query)
        except (httpx.HTTPError, ValueError):
            return []
        return [
            SearchResult(
                name=info.name,
                registry=Registry.CRAN,
                version=info.latest_version,
                description=info.description,
                url=info.documentation_url,
                score=1.0,
                exact=info.name.casefold() == query.casefold(),
            )
        ]


def _first_url(raw: str) -> str:
    return str(raw).split(",")[0].strip()


def _dependencies(data: dict) -> list[Dependency]:
    raw = data.get("Imports", "")
    if not raw:
        raw = data.get("Depends", "")
    dependencies: list[Dependency] = []
    for item in str(raw).split(","):
        name = item.strip().split("(", 1)[0].strip()
        if name and name.lower() not in {"r", "r (>= 3.5.0)"}:
            dependencies.append(Dependency(name=name))
    return dependencies
