"""Daily package-response cache for registry/GitHub API data."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from secchi.models import (
    AdvisoryReference,
    Dependency,
    DownloadCounts,
    DownloadTrendPoint,
    GitHubIssueEvent,
    GitHubStats,
    MetricTimelinePoint,
    PackageInfo,
    Registry,
    ReleaseFile,
    ReverseDependency,
    SecurityAdvisory,
    Version,
)
from secchi.schema import CACHE_SCHEMA_VERSION, SECURITY_CACHE_SCHEMA_VERSION
from secchi.schemas import CacheEnvelope


def cache_root() -> Path:
    """XDG_CACHE_HOME/secchi, else ~/.cache/secchi."""
    if base := os.environ.get("XDG_CACHE_HOME", ""):
        return Path(base) / "secchi"
    return Path.home() / ".cache" / "secchi"


def package_cache_path(key: str, *, root: Path | None = None) -> Path:
    safe = key.replace("/", "_").replace(":", "__")
    return (root or cache_root()) / "packages" / f"{safe}.json"


def security_cache_path(key: str, *, root: Path | None = None) -> Path:
    safe = key.replace("/", "_").replace(":", "__")
    return (root or cache_root()) / "security" / f"{safe}.json"


def load_security_cache(
    key: str,
    package_version: str,
    *,
    root: Path | None = None,
    now: Callable[[], datetime] | None = None,
) -> tuple[list[SecurityAdvisory], datetime] | None:
    path = security_cache_path(key, root=root)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        if not isinstance(raw, dict):
            return None
        if raw.get("schema_version") != SECURITY_CACHE_SCHEMA_VERSION:
            return None
        if raw.get("package_version", "") != package_version:
            return None
        fetched_at = _parse_datetime(raw.get("fetched_at"))
        if fetched_at is None:
            return None
        today = (now or (lambda: datetime.now().astimezone()))().date()
        if fetched_at.astimezone().date() != today:
            return None
        advisories = raw.get("advisories", [])
        if not isinstance(advisories, list):
            return None
        if not all(isinstance(item, dict) for item in advisories):
            return None
        return [_decode_advisory(item) for item in advisories], fetched_at
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
        return None


def save_security_cache(
    key: str,
    package_version: str,
    advisories: list[SecurityAdvisory],
    fetched_at: datetime,
    *,
    root: Path | None = None,
) -> None:
    path = security_cache_path(key, root=root)
    payload = {
        "schema_version": SECURITY_CACHE_SCHEMA_VERSION,
        "fetched_at": fetched_at.isoformat(),
        "package_version": package_version,
        "advisories": _encode([asdict(advisory) for advisory in advisories]),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    except OSError:
        pass


def load_package_cache(
    key: str,
    *,
    root: Path | None = None,
    now: Callable[[], datetime] | None = None,
) -> tuple[PackageInfo, datetime] | None:
    path = package_cache_path(key, root=root)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        if not isinstance(raw, dict):
            return None
        schema_version = raw.get("schema_version", 0)
        if not isinstance(schema_version, int) or schema_version > CACHE_SCHEMA_VERSION:
            return None
        envelope = CacheEnvelope.model_validate(
            {**raw, "schema_version": schema_version}
        )
        fetched_at = envelope.fetched_at
        today = (now or (lambda: datetime.now().astimezone()))().date()
        if fetched_at.astimezone().date() != today:
            return None
        return _decode_package_info(envelope.package), fetched_at
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
        return None


def save_package_cache(
    key: str,
    info: PackageInfo,
    fetched_at: datetime,
    *,
    root: Path | None = None,
) -> None:
    path = package_cache_path(key, root=root)
    payload = CacheEnvelope(
        schema_version=CACHE_SCHEMA_VERSION,
        fetched_at=fetched_at,
        package=_encode(asdict(info)),
    ).model_dump(mode="json")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    except OSError:
        pass


def _encode(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Registry):
        return value.value
    if isinstance(value, dict):
        return {str(k): _encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_encode(v) for v in value]
    return value


def _decode_package_info(raw: dict[str, Any]) -> PackageInfo:
    info = PackageInfo(
        name=raw.get("name", ""),
        registry=Registry(raw.get("registry", "pypi")),
        source_registries=[Registry(r) for r in raw.get("source_registries", []) if r],
        description=raw.get("description", ""),
        author=raw.get("author", ""),
        license=raw.get("license", ""),
        homepage=raw.get("homepage", ""),
        repository_url=raw.get("repository_url", ""),
        documentation_url=raw.get("documentation_url", ""),
        latest_version=raw.get("latest_version", ""),
        latest_release_date=_parse_datetime(raw.get("latest_release_date")),
        total_downloads=raw.get("total_downloads", 0),
        package_kind=raw.get("package_kind", ""),
    )
    info.download_counts = _decode_download_counts(raw.get("download_counts", {}))
    info.github_stats = _decode_github_stats(raw.get("github_stats", {}))
    info.versions = [_decode_version(v) for v in raw.get("versions", [])]
    info.dependencies = [_decode_dependency(d) for d in raw.get("dependencies", [])]
    info.download_trend = [
        DownloadTrendPoint(date=p.get("date", ""), count=p.get("count", 0))
        for p in raw.get("download_trend", [])
    ]
    info.release_notes = raw.get("release_notes", "")
    info.latest_release_files = [
        ReleaseFile(
            packagetype=f.get("packagetype", ""),
            size=f.get("size", 0),
            filename=f.get("filename", ""),
        )
        for f in raw.get("latest_release_files", [])
    ]
    info.version_downloads_recent = {
        _decode_key(k): v for k, v in raw.get("version_downloads_recent", {}).items()
    }
    info.reverse_dependencies = [
        ReverseDependency(name=d.get("name", ""), downloads=d.get("downloads", 0))
        for d in raw.get("reverse_dependencies", [])
    ]
    info.reverse_dependency_count = raw.get("reverse_dependency_count")
    info.reverse_dependency_monthly_growth = raw.get(
        "reverse_dependency_monthly_growth"
    )
    info.health_history = [
        MetricTimelinePoint(label=p.get("label", ""), value=p.get("value", 0))
        for p in raw.get("health_history", [])
    ]
    info.github_issue_events = [
        _decode_issue_event(e) for e in raw.get("github_issue_events", [])
    ]
    info.security_advisories = [
        _decode_advisory(a) for a in raw.get("security_advisories", [])
    ]
    return info


def _decode_download_counts(raw: dict[str, Any]) -> DownloadCounts:
    return DownloadCounts(
        today=raw.get("today", 0),
        week=raw.get("week", 0),
        month=raw.get("month", 0),
    )


def _decode_github_stats(raw: dict[str, Any]) -> GitHubStats:
    return GitHubStats(
        stars=raw.get("stars", 0),
        forks=raw.get("forks", 0),
        open_issues=raw.get("open_issues", 0),
        created_at=_parse_datetime(raw.get("created_at")),
        pushed_at=_parse_datetime(raw.get("pushed_at")),
        has_ci=raw.get("has_ci", False),
        has_readme=raw.get("has_readme", False),
        resolved=raw.get("resolved", False),
        stars_delta_7d=raw.get("stars_delta_7d"),
        open_issues_delta_7d=raw.get("open_issues_delta_7d"),
    )


def _decode_version(raw: dict[str, Any]) -> Version:
    return Version(
        version=raw.get("version", ""),
        release_date=_parse_datetime(raw.get("release_date")),
        downloads=raw.get("downloads", 0),
        is_yanked=raw.get("is_yanked", False),
        external_id=raw.get("external_id"),
        size_bytes=raw.get("size_bytes"),
    )


def _decode_dependency(raw: dict[str, Any]) -> Dependency:
    return Dependency(
        name=raw.get("name", ""),
        requirement=raw.get("requirement", ""),
        optional=raw.get("optional", False),
    )


def _decode_issue_event(raw: dict[str, Any]) -> GitHubIssueEvent:
    return GitHubIssueEvent(
        number=raw.get("number", 0),
        title=raw.get("title", ""),
        is_pull_request=raw.get("is_pull_request", False),
        created_at=_parse_datetime(raw.get("created_at")) or datetime.min,
        closed_at=_parse_datetime(raw.get("closed_at")),
        url=raw.get("url", ""),
    )


def _decode_advisory(raw: dict[str, Any]) -> SecurityAdvisory:
    return SecurityAdvisory(
        id=raw.get("id", ""),
        summary=raw.get("summary", ""),
        details=raw.get("details", ""),
        aliases=raw.get("aliases", []),
        severity=raw.get("severity", ""),
        published=_parse_datetime(raw.get("published")),
        modified=_parse_datetime(raw.get("modified")),
        fixed_versions=raw.get("fixed_versions", []),
        references=[
            AdvisoryReference(type=item.get("type", ""), url=item.get("url", ""))
            for item in raw.get("references", [])
            if isinstance(item, dict)
        ],
        url=raw.get("url", ""),
    )


def _parse_datetime(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def _decode_key(raw: str) -> int | str:
    try:
        return int(raw)
    except ValueError:
        return raw
