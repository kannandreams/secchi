"""pub.dev adapter for Dart and Flutter packages."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx

from secchi.api.sparse import SparseAdapter
from secchi.models import (
    Dependency,
    DownloadCounts,
    PackageInfo,
    Registry,
    SearchResult,
    Version,
)

PUB_API = "https://pub.dev/api"

_MIN_DATETIME = datetime.min.replace(tzinfo=UTC)


class PubDevAdapter(SparseAdapter):
    @property
    def registry(self) -> Registry:
        return Registry.PUB

    async def fetch_package(self, name: str) -> PackageInfo:
        async with self._client_scope() as client:
            response = await client.get(f"{PUB_API}/packages/{name}")
            response.raise_for_status()
            data = response.json()
        package_name = data.get("name", name)
        latest = data.get("latest", {})
        pubspec = latest.get("pubspec", {})
        repository = pubspec.get("repository", "") or pubspec.get("homepage", "")
        return PackageInfo(
            name=package_name,
            registry=Registry.PUB,
            description=pubspec.get("description", "").strip(),
            author=pubspec.get("author", "") or "",
            homepage=pubspec.get("homepage", "") or repository,
            repository_url=repository,
            documentation_url=pubspec.get("documentation", "")
            or f"https://pub.dev/packages/{package_name}",
            latest_version=latest.get("version", "") or pubspec.get("version", ""),
            latest_release_date=_parse_time(latest.get("published")),
            versions=_versions(data.get("versions", [])),
            dependencies=_dependencies(pubspec),
            package_kind="Flutter Package" if _is_flutter(pubspec) else "Dart Package",
            download_counts=await self.fetch_download_counts(package_name),
        )

    async def fetch_versions(self, name: str) -> list[Version]:
        async with self._client_scope() as client:
            response = await client.get(f"{PUB_API}/packages/{name}")
            response.raise_for_status()
            data = response.json()
        return _versions(data.get("versions", []))

    async def fetch_dependencies(self, name: str, version: str) -> list[Dependency]:
        async with self._client_scope() as client:
            response = await client.get(f"{PUB_API}/packages/{name}")
            response.raise_for_status()
            data = response.json()
        for entry in data.get("versions", []):
            if entry.get("version") == version:
                return _dependencies(entry.get("pubspec", {}))
        return []

    async def fetch_download_counts(self, name: str) -> DownloadCounts:
        # pub.dev only exposes a rolling 30-day count, no daily/weekly split
        # and no historical time series.
        async with self._client_scope() as client:
            try:
                response = await client.get(f"{PUB_API}/packages/{name}/score")
                response.raise_for_status()
            except httpx.HTTPError:
                return DownloadCounts()
            data = response.json()
        return DownloadCounts(month=data.get("downloadCount30Days") or 0)

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        async with self._client_scope() as client:
            try:
                response = await client.get(f"{PUB_API}/search", params={"q": query})
                response.raise_for_status()
            except httpx.HTTPError:
                return []
            names = [
                entry.get("package", "")
                for entry in response.json().get("packages", [])[:limit]
                if entry.get("package")
            ]

            async def describe(candidate: str) -> SearchResult | None:
                try:
                    pkg_response = await client.get(f"{PUB_API}/packages/{candidate}")
                    pkg_response.raise_for_status()
                except httpx.HTTPError:
                    return None
                data = pkg_response.json()
                resolved_name = data.get("name", candidate)
                latest = data.get("latest", {})
                pubspec = latest.get("pubspec", {})
                return SearchResult(
                    name=resolved_name,
                    registry=Registry.PUB,
                    version=latest.get("version", ""),
                    description=pubspec.get("description", "").strip(),
                    url=f"https://pub.dev/packages/{resolved_name}",
                    score=1.0,
                    exact=resolved_name.casefold() == query.casefold(),
                )

            results = await asyncio.gather(*(describe(name) for name in names))
        return [result for result in results if result is not None]


def _is_flutter(pubspec: dict) -> bool:
    if "flutter" in pubspec.get("dependencies", {}):
        return True
    return "flutter" in pubspec.get("environment", {})


def _requirement(raw: object) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return "git" if "git" in raw else "path" if "path" in raw else ""
    return ""


def _dependencies(pubspec: dict) -> list[Dependency]:
    deps: list[Dependency] = []
    for dep_name, requirement in pubspec.get("dependencies", {}).items():
        deps.append(Dependency(name=dep_name, requirement=_requirement(requirement)))
    for dep_name, requirement in pubspec.get("dev_dependencies", {}).items():
        deps.append(
            Dependency(
                name=dep_name, requirement=_requirement(requirement), optional=True
            )
        )
    return deps


def _versions(raw: list[dict]) -> list[Version]:
    versions: list[Version] = []
    for entry in raw:
        version = entry.get("version") or entry.get("pubspec", {}).get("version", "")
        if not version:
            continue
        versions.append(
            Version(
                version=version,
                release_date=_parse_time(entry.get("published")),
                is_yanked=bool(entry.get("retracted", False)),
            )
        )
    versions.sort(key=lambda v: v.release_date or _MIN_DATETIME, reverse=True)
    return versions


def _parse_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
