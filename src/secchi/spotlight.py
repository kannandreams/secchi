"""Product-controlled Spotlight feed for the sidebar promo card."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from secchi.cache import cache_root


SPOTLIGHT_URL = "https://secchi.dev/spotlight.json"
DISABLE_ENV = "SECCHI_DISABLE_SPOTLIGHT"
MAX_RESPONSE_BYTES = 8_192


@dataclass(frozen=True)
class Spotlight:
    title: str
    description: str
    url: str
    accent: str = ""
    expires_at: datetime | None = None


FALLBACK_SPOTLIGHT = Spotlight(
    title="tuffcli",
    description="Capability manager",
    url="github.com/kannandreams/tuff",
    accent="blue",
)


def spotlight_disabled() -> bool:
    raw = os.environ.get(DISABLE_ENV, "")
    return raw.lower() in {"1", "true", "yes", "on"}


def spotlight_cache_path() -> Path:
    return cache_root() / "spotlight.json"


def load_cached_spotlight() -> Spotlight | None:
    path = spotlight_cache_path()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        fetched_at = _parse_datetime(raw.get("fetched_at"))
        today = datetime.now().astimezone().date()
        if fetched_at is None or fetched_at.astimezone().date() != today:
            return None
        return _decode_spotlight(raw.get("spotlight", {}))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def save_cached_spotlight(spotlight: Spotlight, fetched_at: datetime) -> None:
    path = spotlight_cache_path()
    payload = {
        "fetched_at": fetched_at.astimezone().isoformat(),
        "spotlight": {
            "title": spotlight.title,
            "description": spotlight.description,
            "url": spotlight.url,
            "accent": spotlight.accent,
            "expires_at": spotlight.expires_at.isoformat()
            if spotlight.expires_at
            else "",
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    except OSError:
        pass


async def fetch_spotlight() -> Spotlight | None:
    if spotlight_disabled():
        return None

    cached = load_cached_spotlight()
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=2.0, follow_redirects=True) as client:
            response = await client.get(SPOTLIGHT_URL)
            response.raise_for_status()
            body = response.content
            if len(body) > MAX_RESPONSE_BYTES:
                return FALLBACK_SPOTLIGHT
            spotlight = _decode_spotlight(json.loads(body.decode("utf-8")))
            save_cached_spotlight(spotlight, datetime.now().astimezone())
            return spotlight
    except (httpx.HTTPError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return FALLBACK_SPOTLIGHT


def _decode_spotlight(raw: dict[str, Any]) -> Spotlight:
    title = _clean_text(raw.get("title", ""), max_len=28)
    description = _clean_text(raw.get("description", ""), max_len=72)
    url = _clean_url(raw.get("url", ""))
    accent = _clean_text(raw.get("accent", ""), max_len=16)
    expires_at = _parse_datetime(raw.get("expires_at"))
    if not title or not description or not url:
        raise ValueError("Spotlight requires title, description, and url")
    if expires_at and expires_at.astimezone() < datetime.now().astimezone():
        raise ValueError("Spotlight has expired")
    return Spotlight(
        title=title,
        description=description,
        url=url,
        accent=accent,
        expires_at=expires_at,
    )


def _clean_text(value: Any, *, max_len: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text[:max_len]


def _clean_url(value: Any) -> str:
    url = str(value or "").replace("\n", "").strip()
    if url.startswith("https://"):
        url = url[len("https://") :]
    elif url.startswith("http://"):
        url = url[len("http://") :]
    if not url or " " in url:
        raise ValueError("Invalid Spotlight URL")
    return url[:80].rstrip("/")


def _parse_datetime(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
