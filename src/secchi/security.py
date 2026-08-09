"""OSV-backed security advisory lookup for supported package ecosystems."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from typing import Any

import httpx

from secchi.models import AdvisoryReference, PackageInfo, Registry, SecurityAdvisory

OSV_QUERY_URL = "https://api.osv.dev/v1/query"
OSV_WEB_URL = "https://osv.dev/vulnerability"

# Safety cap on paginated OSV queries. A real package/version is never
# expected to need this many pages; it exists purely to bound the loop
# against a misbehaving or malicious response that keeps returning a
# next_page_token.
_OSV_MAX_PAGES = 20

OSV_ECOSYSTEMS: dict[Registry, str] = {
    Registry.PYPI: "PyPI",
    Registry.NPM: "npm",
    Registry.CRATES: "crates.io",
    Registry.GO: "Go",
    Registry.CRAN: "CRAN",
}


async def fetch_osv_advisories(
    info: PackageInfo, *, client: httpx.AsyncClient
) -> list[SecurityAdvisory]:
    """Return advisories affecting ``info.latest_version``."""
    ecosystem = OSV_ECOSYSTEMS.get(info.registry)
    if not ecosystem or not info.latest_version:
        return []

    advisories: list[SecurityAdvisory] = []
    page_token: str | None = None
    for _ in range(_OSV_MAX_PAGES):
        query: dict[str, Any] = {
            "package": {"name": info.name, "ecosystem": ecosystem},
            "version": info.latest_version,
        }
        if page_token:
            query["page_token"] = page_token

        response = await client.post(OSV_QUERY_URL, json=query)
        response.raise_for_status()
        payload = response.json()

        advisories.extend(
            advisory
            for raw in payload.get("vulns", [])
            if isinstance(raw, dict)
            and not raw.get("withdrawn")
            and (advisory := _parse_advisory(raw)) is not None
        )

        page_token = payload.get("next_page_token")
        if not page_token:
            break

    return advisories


def _parse_advisory(raw: dict[str, Any]) -> SecurityAdvisory | None:
    advisory_id = raw.get("id")
    if not isinstance(advisory_id, str) or not advisory_id:
        return None

    affected = raw.get("affected", [])
    if not isinstance(affected, list):
        affected = []
    fixed_versions = sorted(
        {
            event["fixed"]
            for item in affected
            if isinstance(item, dict)
            for range_item in item.get("ranges", [])
            if isinstance(range_item, dict)
            for event in range_item.get("events", [])
            if isinstance(event, dict) and isinstance(event.get("fixed"), str)
        }
    )
    references = [
        AdvisoryReference(type=item.get("type", ""), url=item["url"])
        for item in raw.get("references", [])
        if isinstance(item, dict) and isinstance(item.get("url"), str)
    ]
    return SecurityAdvisory(
        id=advisory_id,
        summary=raw.get("summary", "") or "",
        details=raw.get("details", "") or "",
        aliases=[alias for alias in raw.get("aliases", []) if isinstance(alias, str)],
        severity=_severity(raw, affected),
        published=_parse_datetime(raw.get("published")),
        modified=_parse_datetime(raw.get("modified")),
        fixed_versions=fixed_versions,
        references=references,
        url=f"{OSV_WEB_URL}/{advisory_id}",
    )


def _severity(raw: dict[str, Any], affected: list[Any]) -> str:
    for item in affected:
        if not isinstance(item, dict):
            continue
        for source in (item.get("ecosystem_specific"), item.get("database_specific")):
            if isinstance(source, dict):
                value = source.get("severity")
                if isinstance(value, str) and value:
                    return value.upper()
    for item in raw.get("severity", []):
        if isinstance(item, dict):
            score = item.get("score")
            if isinstance(score, str) and score:
                return score
    return ""


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    with suppress(ValueError, TypeError):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None
