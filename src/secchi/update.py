"""Best-effort notification when a newer Secchi release is available."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

from secchi import __version__
from secchi.cache import cache_root

PYPI_URL = "https://pypi.org/pypi/secchi/json"
UPDATE_CACHE_TTL = timedelta(days=1)
UPDATE_CACHE_PATH = cache_root() / "update-check.json"
DISABLE_UPDATE_ENV = "SECCHI_DISABLE_UPDATE_CHECK"


@dataclass(frozen=True)
class UpdateNotice:
    """A newer release and the version currently running."""

    current_version: str
    latest_version: str

    @property
    def message(self) -> str:
        return (
            f"A newer Secchi version is available: {self.latest_version} "
            f"(current: {self.current_version}). Upgrade with: "
            "pipx upgrade secchi or uv tool upgrade secchi"
        )


def update_check_disabled() -> bool:
    """Return whether the user opted out of release checks."""

    return os.environ.get(DISABLE_UPDATE_ENV, "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def check_for_update(
    *,
    current_version: str = __version__,
    cache_path: Path | None = None,
    now: Callable[[], datetime] | None = None,
    fetch: Callable[[], dict[str, Any]] | None = None,
) -> UpdateNotice | None:
    """Return a notice for a newer PyPI release, without failing the command.

    The result is cached for one day. Network, filesystem, and malformed
    response errors intentionally produce no notice and never affect Secchi's
    primary command.
    """

    if update_check_disabled():
        return None

    clock = now or (lambda: datetime.now(UTC))
    path = cache_path or UPDATE_CACHE_PATH
    payload = _load_cache(path, clock())
    if payload is None:
        try:
            payload = (fetch or _fetch_latest)()
        except (OSError, httpx.HTTPError, ValueError, TypeError, KeyError):
            return None
        _save_cache(path, payload, clock())

    latest = payload.get("latest_version", "")
    if not isinstance(latest, str) or not _is_newer(latest, current_version):
        return None
    return UpdateNotice(current_version=current_version, latest_version=latest)


def _fetch_latest() -> dict[str, Any]:
    response = httpx.get(PYPI_URL, timeout=2.0)
    response.raise_for_status()
    data = response.json()
    return {"latest_version": data["info"]["version"]}


def _load_cache(path: Path, now: datetime) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text())
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if now - fetched_at > UPDATE_CACHE_TTL:
            return None
        return data
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _save_cache(path: Path, payload: dict[str, Any], fetched_at: datetime) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {**payload, "fetched_at": fetched_at.isoformat()},
                sort_keys=True,
            )
        )
    except OSError:
        pass


def _is_newer(latest: str, current: str) -> bool:
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        return False
