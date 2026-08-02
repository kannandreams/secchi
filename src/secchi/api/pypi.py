"""PyPI registry adapter using PyPI JSON API."""

from __future__ import annotations

import re
from contextlib import suppress
from datetime import datetime
from html import unescape
from typing import Any

import httpx

from secchi.api.base import AdapterBase, RegistryAdapter
from secchi.models import (
    Dependency,
    DownloadCounts,
    DownloadTrendPoint,
    PackageInfo,
    Registry,
    ReleaseFile,
    SearchResult,
    Version,
)

PYPI_JSON = "https://pypi.org/pypi"
PYPI_STATS = "https://pypistats.org/api"


def _derive_kind(classifiers: list[str]) -> str:
    """Best-effort package kind from PyPI trove classifiers."""
    text = " ".join(classifiers)
    if "Environment :: Console" in text or "Topic :: Utilities" in text:
        return "CLI"
    return "Library"


class PyPIAdapter(AdapterBase, RegistryAdapter):
    @property
    def registry(self) -> Registry:
        return Registry.PYPI

    async def _get_json(self, name: str, client: httpx.AsyncClient) -> dict[str, Any]:
        resp = await client.get(f"{PYPI_JSON}/{name}/json")
        resp.raise_for_status()
        return resp.json()

    async def fetch_package(self, name: str) -> PackageInfo:
        async with self._client_scope() as client:
            data = await self._get_json(name, client)
            info = data["info"]

            latest_version = info.get("version", "")
            versions_data = data.get("releases", {})
            latest_files = versions_data.get(latest_version, [])
            upload_time = None
            if latest_files:
                upload_time_raw = latest_files[0].get("upload_time", "")
                if upload_time_raw:
                    with suppress(ValueError, TypeError):
                        upload_time = datetime.fromisoformat(
                            upload_time_raw.replace("Z", "+00:00")
                        )

            release_files = [
                ReleaseFile(
                    packagetype=f.get("packagetype", "") or "",
                    size=f.get("size", 0) or 0,
                    filename=f.get("filename", "") or "",
                )
                for f in latest_files
            ]

            project_urls = info.get("project_urls") or {}
            homepage = info.get("home_page", "")
            repo_url = project_urls.get("Source", "")
            if not repo_url:
                repo_url = project_urls.get("Repository", "")
            if not repo_url:
                repo_url = project_urls.get("Source Code", "")
            docs_url = info.get("docs_url", "")
            if not docs_url:
                docs_url = project_urls.get("Documentation", "")

            return PackageInfo(
                name=info["name"],
                registry=Registry.PYPI,
                description=info.get("summary", ""),
                author=info.get("author", ""),
                license=info.get("license", ""),
                homepage=homepage,
                repository_url=repo_url,
                documentation_url=docs_url,
                latest_version=latest_version,
                latest_release_date=upload_time,
                package_kind=_derive_kind(info.get("classifiers", []) or []),
                latest_release_files=release_files,
            )

    async def fetch_versions(self, name: str) -> list[Version]:
        async with self._client_scope() as client:
            data = await self._get_json(name, client)
            versions_data = data.get("releases", {})

            versions: list[Version] = []
            for ver_str, files in versions_data.items():
                upload_time = None
                for f in files:
                    raw = f.get("upload_time", "")
                    if raw:
                        try:
                            upload_time = datetime.fromisoformat(
                                raw.replace("Z", "+00:00")
                            )
                            break
                        except (ValueError, TypeError):
                            pass

                yanked = any(f.get("yanked", False) for f in files)
                size = sum(f.get("size", 0) or 0 for f in files) or None

                versions.append(
                    Version(
                        version=ver_str,
                        release_date=upload_time,
                        is_yanked=yanked,
                        size_bytes=size,
                    )
                )

            versions.sort(key=lambda v: v.release_date or datetime.min, reverse=True)
            return versions

    async def fetch_dependencies(self, name: str, version: str) -> list[Dependency]:
        async with self._client_scope() as client:
            data = await self._get_json(name, client)
            info = data["info"]
            requires_dist = info.get("requires_dist") or []

            deps: list[Dependency] = []
            for raw in requires_dist:
                if not raw:
                    continue
                if "extra ==" in raw:
                    continue
                raw_clean = raw.split(";")[0].strip()
                if not raw_clean:
                    continue
                parts = raw_clean.split()
                dep_name = parts[0].strip()
                requirement = " ".join(parts[1:]) if len(parts) > 1 else ""
                deps.append(Dependency(name=dep_name, requirement=requirement))

            return deps

    async def fetch_download_trend(
        self, name: str, days: int = 30
    ) -> list[DownloadTrendPoint]:
        async with self._client_scope() as client:
            try:
                resp = await client.get(
                    f"{PYPI_STATS}/packages/{name}/overall",
                    params={"mirrors": "false"},
                )
                resp.raise_for_status()
                stats_data = resp.json()
            except httpx.HTTPError:
                return []

            raw_data = stats_data.get("data", [])
            points = [
                DownloadTrendPoint(
                    date=entry.get("date", ""),
                    count=entry.get("downloads", 0),
                )
                for entry in raw_data
            ]
            points.sort(key=lambda p: p.date)
            return points[-days:] if len(points) > days else points

    async def fetch_download_counts(self, name: str) -> DownloadCounts:
        async with self._client_scope() as client:
            try:
                resp = await client.get(
                    f"{PYPI_STATS}/packages/{name}/recent",
                    params={"mirrors": "false"},
                )
                resp.raise_for_status()
                data = resp.json()
                period_data = data.get("data", {})
                return DownloadCounts(
                    today=period_data.get("last_day", 0),
                    week=period_data.get("last_week", 0),
                    month=period_data.get("last_month", 0),
                )
            except httpx.HTTPError:
                pass

        # Fallback: compute from trend data
        trend = await self.fetch_download_trend(name, days=30)
        if not trend:
            return DownloadCounts()
        return DownloadCounts(
            today=trend[-1].count if trend else 0,
            week=sum(p.count for p in trend[-7:]),
            month=sum(p.count for p in trend),
        )

    async def fetch_release_notes(self, name: str, version: str) -> str:
        return ""  # fetched via GitHub in utils

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search PyPI's public search page (the JSON API has no search route)."""
        async with self._client_scope() as client:
            # PyPI's JSON API is dependable for exact package resolution even
            # when its HTML search page changes markup or is unavailable.
            try:
                exact_response = await client.get(f"{PYPI_JSON}/{query}/json")
                exact_response.raise_for_status()
                exact_info = exact_response.json().get("info", {})
                return [
                    SearchResult(
                        name=exact_info.get("name", query),
                        registry=Registry.PYPI,
                        version=exact_info.get("version", ""),
                        description=exact_info.get("summary", "") or "",
                        url=f"https://pypi.org/project/{exact_info.get('name', query)}/",
                        score=1.0,
                        exact=True,
                    )
                ]
            except (httpx.HTTPError, ValueError, KeyError):
                pass
            try:
                response = await client.get(
                    "https://pypi.org/search/",
                    params={"q": query, "page": 1},
                    headers={"Accept": "text/html"},
                )
                response.raise_for_status()
            except httpx.HTTPError:
                return []

        pattern = re.compile(
            r'data-project-url="([^"]+)"[^>]*>.*?'
            r'class="package-snippet__name">\s*([^<]+).*?'
            r'class="package-snippet__version">\s*([^<]+).*?'
            r'class="package-snippet__description">\s*([^<]*)',
            re.DOTALL,
        )
        results: list[SearchResult] = []
        for url, name, version, description in pattern.findall(response.text)[:limit]:
            clean_name = unescape(name).strip()
            results.append(
                SearchResult(
                    name=clean_name,
                    registry=Registry.PYPI,
                    version=unescape(version).strip(),
                    description=" ".join(unescape(description).split()),
                    url=f"https://pypi.org{url}" if url.startswith("/") else url,
                    exact=clean_name.lower() == query.lower(),
                    score=1.0 if clean_name.lower() == query.lower() else 0.0,
                )
            )
        return results
