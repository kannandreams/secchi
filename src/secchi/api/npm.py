"""npm registry adapter — direct REST API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from secchi.api.base import RegistryAdapter
from secchi.config import get_env_token
from secchi.models import (
    Dependency,
    DownloadCounts,
    DownloadTrendPoint,
    PackageInfo,
    Registry,
    ReleaseFile,
    Version,
)

NPM_REGISTRY = "https://registry.npmjs.org"
NPM_DOWNLOADS = "https://api.npmjs.org/downloads"


def _npm_name(name: str) -> str:
    """URL-encode an npm package name (handles scoped packages like @scope/name)."""
    if "/" in name:
        parts = name.split("/", 1)
        return f"{parts[0]}/{parts[1]}"
    return name


class NpmAdapter(RegistryAdapter):
    @property
    def registry(self) -> Registry:
        return Registry.NPM

    async def fetch_package(self, name: str) -> PackageInfo:
        async with httpx.AsyncClient() as client:
            safe_name = _npm_name(name)
            resp = await client.get(f"{NPM_REGISTRY}/{safe_name}")
            resp.raise_for_status()
            data = resp.json()

            latest_tag = data.get("dist-tags", {}).get("latest", "")
            latest_info = data.get("versions", {}).get(latest_tag, {}) if latest_tag else {}

            description = data.get("description", "")
            author_info = data.get("author", {})
            author = author_info.get("name", "") if isinstance(author_info, dict) else str(author_info) if author_info else ""

            repo_info = data.get("repository", {})
            repo_url = repo_info.get("url", "") if isinstance(repo_info, dict) else str(repo_info) if repo_info else ""

            homepage = data.get("homepage", "")

            if latest_info:
                latest_date = next(
                    (Version(version=v, release_date=_parse_npm_time(data.get("time", {}).get(v)))
                     for v in [latest_tag] if v in data.get("time", {})),
                    Version(version=latest_tag),
                )
                latest_release_date = latest_date.release_date
            else:
                latest_release_date = None

            total_downloads = await self._fetch_total_downloads(name)

            kind = "CLI" if latest_info.get("bin") else "Library"
            release_files: list[ReleaseFile] = []
            unpacked = latest_info.get("dist", {}).get("unpackedSize")
            if unpacked:
                release_files.append(
                    ReleaseFile(
                        packagetype="npm-package",
                        size=unpacked,
                        filename=f"{name}-{latest_tag}.tgz",
                    )
                )

            return PackageInfo(
                name=data["name"],
                registry=Registry.NPM,
                description=description,
                author=author,
                license=latest_info.get("license", ""),
                homepage=homepage,
                repository_url=repo_url,
                latest_version=latest_tag,
                latest_release_date=latest_release_date,
                total_downloads=total_downloads,
                package_kind=kind,
                latest_release_files=release_files,
            )

    async def fetch_versions(self, name: str) -> list[Version]:
        async with httpx.AsyncClient() as client:
            safe_name = _npm_name(name)
            resp = await client.get(f"{NPM_REGISTRY}/{safe_name}")
            resp.raise_for_status()
            data = resp.json()

            versions: list[Version] = []
            time_data = data.get("time", {})
            for ver, info in data.get("versions", {}).items():
                release_date = _parse_npm_time(time_data.get(ver))
                size = info.get("dist", {}).get("unpackedSize") if isinstance(info, dict) else None
                versions.append(
                    Version(
                        version=ver,
                        release_date=release_date,
                        size_bytes=size,
                    )
                )

            versions.sort(key=lambda v: v.release_date or datetime.min, reverse=True)
            return versions

    async def fetch_dependencies(self, name: str, version: str) -> list[Dependency]:
        async with httpx.AsyncClient() as client:
            safe_name = _npm_name(name)
            resp = await client.get(f"{NPM_REGISTRY}/{safe_name}")
            resp.raise_for_status()
            data = resp.json()

            version_data = data.get("versions", {}).get(version, {})
            deps: list[Dependency] = []

            for dep_key, dep_label in [
                ("dependencies", False),
                ("devDependencies", True),
                ("peerDependencies", True),
            ]:
                dep_map = version_data.get(dep_key, {})
                if isinstance(dep_map, dict):
                    for dep_name, req in dep_map.items():
                        deps.append(
                            Dependency(
                                name=dep_name,
                                requirement=str(req),
                                optional=dep_label != "dependencies",
                            )
                        )

            return deps

    async def fetch_download_trend(
        self, name: str, days: int = 30
    ) -> list[DownloadTrendPoint]:
        async with httpx.AsyncClient() as client:
            try:
                if days <= 31:
                    url = f"{NPM_DOWNLOADS}/range/last-month/{name}"
                else:
                    end = datetime.now(timezone.utc).date()
                    start = end - timedelta(days=days)
                    url = f"{NPM_DOWNLOADS}/range/{start:%Y-%m-%d}:{end:%Y-%m-%d}/{name}"
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                return []

            points = [
                DownloadTrendPoint(date=entry["day"], count=entry["downloads"])
                for entry in data.get("downloads", [])
            ]
            return points[-days:] if len(points) > days else points

    async def fetch_download_counts(self, name: str) -> DownloadCounts:
        async with httpx.AsyncClient() as client:
            today = week = month = 0
            for period, store in [
                ("last-day", "today"),
                ("last-week", "week"),
                ("last-month", "month"),
            ]:
                try:
                    resp = await client.get(
                        f"{NPM_DOWNLOADS}/point/{period}/{name}"
                    )
                    resp.raise_for_status()
                    val = resp.json().get("downloads", 0)
                    if store == "today":
                        today = val
                    elif store == "week":
                        week = val
                    else:
                        month = val
                except httpx.HTTPError:
                    pass
            return DownloadCounts(today=today, week=week, month=month)

    async def fetch_release_notes(self, name: str, version: str) -> str:
        async with httpx.AsyncClient() as client:
            safe_name = _npm_name(name)
            resp = await client.get(f"{NPM_REGISTRY}/{safe_name}")
            resp.raise_for_status()
            data = resp.json()

            version_data = data.get("versions", {}).get(version, {})
            readme = version_data.get("readme", "")
            if readme:
                max_chars = 2000
                return readme[:max_chars] + ("..." if len(readme) > max_chars else "")
            return ""

    async def _fetch_total_downloads(self, name: str) -> int:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{NPM_DOWNLOADS}/point/last-year/{name}"
                )
                resp.raise_for_status()
                return resp.json().get("downloads", 0)
            except httpx.HTTPError:
                return 0


def _parse_npm_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
