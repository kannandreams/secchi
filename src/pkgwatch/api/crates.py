"""crates.io registry adapter — direct REST API."""

from __future__ import annotations

from datetime import datetime

import httpx

from pkgwatch.api.base import RegistryAdapter
from pkgwatch.models import (
    Dependency,
    DownloadCounts,
    DownloadTrendPoint,
    PackageInfo,
    Registry,
    Version,
)

CRATES_API = "https://crates.io/api/v1"

_HEADERS = {
    "User-Agent": "pkgwatch (https://github.com/pkgwatch)",
    "Accept": "application/json",
}


class CratesAdapter(RegistryAdapter):
    @property
    def registry(self) -> Registry:
        return Registry.CRATES

    async def fetch_package(self, name: str) -> PackageInfo:
        async with httpx.AsyncClient(headers=_HEADERS) as client:
            resp = await client.get(f"{CRATES_API}/crates/{name}")
            resp.raise_for_status()
            data = resp.json()["crate"]

            latest_version = data.get("max_stable_version", "")
            if not latest_version:
                latest_version = data.get("max_version", "")

            total_downloads = data.get("downloads", 0)

            return PackageInfo(
                name=data["name"],
                registry=Registry.CRATES,
                description=data.get("description", ""),
                license=data.get("license", ""),
                homepage=data.get("homepage", ""),
                repository_url=data.get("repository", ""),
                documentation_url=data.get("documentation", ""),
                latest_version=latest_version,
                latest_release_date=_parse_date(data.get("updated_at")),
                total_downloads=total_downloads,
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

    async def fetch_release_notes(self, name: str, version: str) -> str:
        return ""  # fetched via GitHub in utils


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        raw_clean = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(raw_clean)
    except (ValueError, TypeError):
        return None
