"""crates.io registry adapter — direct REST API."""

from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from secchi.api.base import RegistryAdapter
from secchi.models import (
    Dependency,
    DownloadCounts,
    DownloadTrendPoint,
    PackageInfo,
    Registry,
    ReleaseFile,
    ReverseDependency,
    SearchResult,
    Version,
)

CRATES_API = "https://crates.io/api/v1"

_HEADERS = {
    "User-Agent": "secchi (https://github.com/secchi)",
    "Accept": "application/json",
}

# crates.io category slugs / names that indicate a CLI tool.
_CLI_CATEGORIES = {
    "command-line-utilities",
    "command-line-interface",
    "development-tools::cargo-plugins",
}


class CratesAdapter(RegistryAdapter):
    @property
    def registry(self) -> Registry:
        return Registry.CRATES

    async def fetch_package(self, name: str) -> PackageInfo:
        async with httpx.AsyncClient(headers=_HEADERS) as client:
            resp = await client.get(f"{CRATES_API}/crates/{name}")
            resp.raise_for_status()
            payload = resp.json()
            data = payload["crate"]

            latest_version = data.get("max_stable_version", "")
            if not latest_version:
                latest_version = data.get("max_version", "")

            total_downloads = data.get("downloads", 0)

            # package_kind from categories (best-effort; never blocks the fetch)
            kind = "Library"
            for cat in payload.get("categories", []):
                slug = (cat.get("slug") or "").lower()
                if slug in _CLI_CATEGORIES:
                    kind = "CLI"
                    break

            # synthetic release file for the latest version's crate size;
            # license lives on the version object, not the top-level crate.
            release_files: list[ReleaseFile] = []
            license = data.get("license", "") or ""
            for ver in payload.get("versions", []):
                if ver.get("num") == latest_version:
                    release_files.append(
                        ReleaseFile(
                            packagetype="crate",
                            size=ver.get("crate_size") or 0,
                            filename=f"{name}-{latest_version}.crate",
                        )
                    )
                    license = license or ver.get("license", "") or ""
                    break
            if not license:
                for ver in payload.get("versions", []):
                    if ver.get("license"):
                        license = ver["license"]
                        break

            return PackageInfo(
                name=data["name"],
                registry=Registry.CRATES,
                description=data.get("description", ""),
                license=license,
                homepage=data.get("homepage", ""),
                repository_url=data.get("repository", ""),
                documentation_url=data.get("documentation", ""),
                latest_version=latest_version,
                latest_release_date=_parse_date(data.get("updated_at")),
                total_downloads=total_downloads,
                package_kind=kind,
                latest_release_files=release_files,
            )

    async def fetch_versions(self, name: str) -> list[Version]:
        async with httpx.AsyncClient(headers=_HEADERS) as client:
            resp = await client.get(f"{CRATES_API}/crates/{name}")
            resp.raise_for_status()
            data = resp.json()

            versions: list[Version] = []
            for ver_data in data.get("versions", []):
                versions.append(
                    Version(
                        version=ver_data["num"],
                        release_date=_parse_date(ver_data.get("created_at")),
                        downloads=ver_data.get("downloads", 0),
                        is_yanked=ver_data.get("yanked", False),
                        external_id=ver_data.get("id"),
                        size_bytes=ver_data.get("crate_size"),
                    )
                )

            versions.sort(key=lambda v: v.release_date or datetime.min, reverse=True)
            return versions

    async def fetch_dependencies(self, name: str, version: str) -> list[Dependency]:
        async with httpx.AsyncClient(headers=_HEADERS) as client:
            resp = await client.get(
                f"{CRATES_API}/crates/{name}/{version}/dependencies"
            )
            resp.raise_for_status()
            data = resp.json()

            deps: list[Dependency] = []
            for dep in data.get("dependencies", []):
                deps.append(
                    Dependency(
                        name=dep["crate_id"],
                        requirement=dep.get("req", "*"),
                        optional=dep.get("optional", False),
                    )
                )
            return deps

    async def fetch_download_trend(
        self, name: str, days: int = 30
    ) -> list[DownloadTrendPoint]:
        async with httpx.AsyncClient(headers=_HEADERS) as client:
            resp = await client.get(f"{CRATES_API}/crates/{name}/downloads")
            resp.raise_for_status()
            data = resp.json()

            daily: dict[str, int] = {}
            for entry in data.get("version_downloads", []):
                date = entry["date"]
                daily[date] = daily.get(date, 0) + entry.get("downloads", 0)

            for entry in data.get("meta", {}).get("extra_downloads", []):
                date = entry["date"]
                daily[date] = daily.get(date, 0) + entry.get("downloads", 0)

            points = [
                DownloadTrendPoint(date=date, count=count)
                for date, count in sorted(daily.items())
            ]
            return points[-days:] if len(points) > days else points

    async def fetch_download_counts(self, name: str) -> DownloadCounts:
        trend = await self.fetch_download_trend(name, days=30)
        if not trend:
            return DownloadCounts()

        today = trend[-1].count if trend else 0
        week = sum(p.count for p in trend[-7:])
        month = sum(p.count for p in trend)
        return DownloadCounts(today=today, week=week, month=month)

    async def fetch_version_download_breakdown(
        self, name: str
    ) -> dict[int | str, int]:
        """Sum version_downloads per crates.io numeric version id.

        Real per-version signal — the numeric id joins to Version.external_id.
        """
        async with httpx.AsyncClient(headers=_HEADERS) as client:
            try:
                resp = await client.get(f"{CRATES_API}/crates/{name}/downloads")
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                return {}
            totals: dict[int | str, int] = {}
            for entry in data.get("version_downloads", []):
                vid = entry.get("version")
                if vid is None:
                    continue
                totals[vid] = totals.get(vid, 0) + entry.get("downloads", 0)
            return totals

    async def fetch_reverse_dependencies(
        self, name: str, limit: int = 5
    ) -> list[ReverseDependency]:
        """Reverse dependencies ranked by each dependent's real total downloads."""
        async with httpx.AsyncClient(headers=_HEADERS) as client:
            try:
                resp = await client.get(
                    f"{CRATES_API}/crates/{name}/reverse_dependencies",
                    params={"per_page": "30", "sort": "downloads"},
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                return []

            # Join dependency edges -> version -> owning crate name.
            versions = {v.get("id"): v.get("crate") for v in data.get("versions", [])}
            names: list[str] = []
            seen: set[str] = set()
            for dep in data.get("dependencies", []):
                crate_name = versions.get(dep.get("version_id"))
                if crate_name and crate_name not in seen:
                    seen.add(crate_name)
                    names.append(crate_name)
                if len(names) >= 10:
                    break

            async def _downloads(crate_name: str) -> ReverseDependency:
                try:
                    r = await client.get(f"{CRATES_API}/crates/{crate_name}")
                    r.raise_for_status()
                    dl = r.json()["crate"].get("downloads", 0)
                except (httpx.HTTPError, KeyError):
                    dl = 0
                return ReverseDependency(name=crate_name, downloads=dl)

            results = await asyncio.gather(*[_downloads(n) for n in names])
            results.sort(key=lambda r: r.downloads, reverse=True)
            return results[:limit]

    async def fetch_reverse_dependency_count(self, name: str) -> int | None:
        async with httpx.AsyncClient(headers=_HEADERS) as client:
            try:
                resp = await client.get(
                    f"{CRATES_API}/crates/{name}/reverse_dependencies",
                    params={"per_page": "1"},
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                return None

        return _reverse_dependency_total(data)

    async def fetch_release_notes(self, name: str, version: str) -> str:
        return ""  # fetched via GitHub in utils

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        async with httpx.AsyncClient(headers=_HEADERS) as client:
            try:
                response = await client.get(
                    f"{CRATES_API}/crates",
                    params={"q": query, "per_page": limit},
                )
                response.raise_for_status()
            except httpx.HTTPError:
                return []
        results: list[SearchResult] = []
        for crate in response.json().get("crates", [])[:limit]:
            name = crate.get("id", crate.get("name", ""))
            results.append(
                SearchResult(
                    name=name,
                    registry=Registry.CRATES,
                    version=crate.get("max_version", ""),
                    description=crate.get("description", "") or "",
                    url=f"https://crates.io/crates/{name}",
                    score=float(crate.get("recent_downloads", 0) or 0),
                    exact=name.lower() == query.lower(),
                )
            )
        return results


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        raw_clean = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(raw_clean)
    except (ValueError, TypeError):
        return None


def _reverse_dependency_total(data: dict) -> int | None:
    meta = data.get("meta", {})
    for key in ("total", "total_count", "count"):
        value = meta.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None
