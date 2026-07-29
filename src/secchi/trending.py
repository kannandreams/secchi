"""GitHub trending card — shows a highly-starred recent repo in the sidebar."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from secchi.cache import cache_root

TRENDING_CACHE = cache_root() / "trending.json"
MAX_RESPONSE_BYTES = 8_192


@dataclass(frozen=True)
class TrendingRepo:
    title: str
    description: str
    url: str
    stars: str
    language: str = ""


FALLBACK_TRENDING = TrendingRepo(
    title="tuffcli",
    description="Capability lifecycle manager for coding agents",
    url="github.com/kannandreams/tuff",
    stars="—",
    language="Rust",
)


def _trending_date() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")


async def fetch_trending() -> TrendingRepo | None:
    try:
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
            response = await client.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"created:>{_trending_date()}",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 1,
                },
                headers={"Accept": "application/vnd.github+json"},
            )
            response.raise_for_status()
            body = response.content
            if len(body) > MAX_RESPONSE_BYTES:
                return FALLBACK_TRENDING
            data = json.loads(body.decode("utf-8"))
            items = data.get("items", [])
            if not items:
                return FALLBACK_TRENDING

            repo = items[0]
            return TrendingRepo(
                title=repo.get("full_name", repo.get("name", "")),
                description=(repo.get("description", "") or "")[:72],
                url=repo.get("html_url", "").replace("https://", "").rstrip("/"),
                stars=_short_stars(repo.get("stargazers_count", 0)),
                language=repo.get("language", "") or "",
            )
    except (httpx.HTTPError, UnicodeDecodeError, json.JSONDecodeError, KeyError):
        return FALLBACK_TRENDING


def _short_stars(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def load_cached_trending() -> TrendingRepo | None:
    path = TRENDING_CACHE
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        fetched_at = _parse_datetime(raw.get("fetched_at"))
        today = datetime.now().astimezone().date()
        if fetched_at is None or fetched_at.astimezone().date() != today:
            return None
        return TrendingRepo(**raw.get("repo", {}))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def save_cached_trending(repo: TrendingRepo) -> None:
    path = TRENDING_CACHE
    payload = {
        "fetched_at": datetime.now().astimezone().isoformat(),
        "repo": {
            "title": repo.title,
            "description": repo.description,
            "url": repo.url,
            "stars": repo.stars,
            "language": repo.language,
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    except OSError:
        pass


def _parse_datetime(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
