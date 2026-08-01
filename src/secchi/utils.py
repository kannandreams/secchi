"""Utility helpers — formatting, GitHub fetching, repo derivation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from secchi.config import get_env_token
from secchi.http import HttpClientFactory
from secchi.models import GitHubIssueEvent, GitHubStats


def shorten_number(n: int) -> str:
    """Format a large number with K, M, B suffixes."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_age(dt: datetime | None) -> str:
    """Human 'time ago' string from a datetime (tz-naive treated as UTC)."""
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - dt).days
    if days < 0:
        days = 0
    if days == 0:
        return "today"
    if days == 1:
        return "1 day ago"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    if days < 365:
        return f"{days // 30} months ago"
    years = days // 365
    return "1 year ago" if years == 1 else f"{years} years ago"


def format_age_short(dt: datetime | None) -> str:
    """Compact 'time ago' — '2d', '3w', '5mo', '2y' — for narrow panels."""
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    days = max((datetime.now(timezone.utc) - dt).days, 0)
    if days == 0:
        return "today"
    if days < 14:
        return f"{days}d"
    if days < 60:
        return f"{days // 7}w"
    if days < 365:
        return f"{days // 30}mo"
    return f"{days // 365}y"


def format_pct_delta(pct: float | None) -> tuple[str, str]:
    """Return (text, rich_color) for a percentage change, or ('—', 'dim')."""
    if pct is None:
        return "—", "dim"
    arrow = "↑" if pct >= 0 else "↓"
    color = "green" if pct >= 0 else "red"
    return f"{arrow} {abs(pct):.1f}%", color


def shorten_bytes(n: int | None) -> str:
    """Format a byte count with B/KB/MB/GB suffixes."""
    if not n:
        return "—"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def derive_github_repo(urls: list[str]) -> tuple[str, str] | None:
    """Try to extract (owner, repo) from a list of URLs.

    Returns None if no GitHub URL is found.
    """
    for url in urls:
        if not url:
            continue
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if "github.com" not in host:
            continue
        path = parsed.path.strip("/")
        if path.endswith(".git"):
            path = path[: -len(".git")]
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] and parts[1]:
            return parts[0], parts[1]
    return None


def _gh_headers() -> dict[str, str]:
    token = get_env_token("SECCHI_GITHUB_TOKEN")
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_gh_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


async def fetch_github_release_notes(
    owner: str,
    repo: str,
    tag: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Fetch the latest release notes from GitHub.

    Uses SECCHI_GITHUB_TOKEN env var for higher rate limits.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    params: dict[str, str] = {"per_page": "5"}

    if client is None:
        async with HttpClientFactory().create() as owned_client:
            return await fetch_github_release_notes(owner, repo, tag, owned_client)
    try:
        resp = await client.get(url, headers=_gh_headers(), params=params)
        resp.raise_for_status()
        releases = resp.json()
    except httpx.HTTPError:
        return ""

    if not releases:
        return ""

    release = releases[0]
    if tag and tag in [r.get("tag_name", "") for r in releases]:
        release = next(r for r in releases if r.get("tag_name") == tag)

    body = release.get("body", "")
    max_chars = 3000
    return body[:max_chars] + ("..." if len(body) > max_chars else "")


async def fetch_github_stats(
    owner: str, repo: str, client: httpx.AsyncClient | None = None
) -> GitHubStats:
    """Fetch GitHub stars, forks, issues, and timestamps for a repo."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    own_client = client is None
    own_client = client is None
    client = client or HttpClientFactory().create()
    try:
        resp = await client.get(url, headers=_gh_headers())
        resp.raise_for_status()
        data = resp.json()
        return GitHubStats(
            stars=data.get("stargazers_count", 0),
            forks=data.get("forks_count", 0),
            open_issues=data.get("open_issues_count", 0),
            created_at=_parse_gh_time(data.get("created_at")),
            pushed_at=_parse_gh_time(data.get("pushed_at")),
            resolved=True,
        )
    except httpx.HTTPError:
        return GitHubStats(resolved=False)
    finally:
        if own_client:
            await client.aclose()


async def fetch_github_repo_signals(
    owner: str, repo: str, client: httpx.AsyncClient
) -> tuple[bool, bool]:
    """Return (has_ci, has_readme).

    has_ci: .github/workflows contents resolves to a non-empty list.
    has_readme: /readme resolves 200. Both best-effort; errors => False.
    """
    has_ci = False
    has_readme = False
    try:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows",
            headers=_gh_headers(),
        )
        if resp.status_code == 200:
            body = resp.json()
            has_ci = isinstance(body, list) and len(body) > 0
    except httpx.HTTPError:
        pass

    try:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/readme",
            headers=_gh_headers(),
        )
        has_readme = resp.status_code == 200
    except httpx.HTTPError:
        pass

    return has_ci, has_readme


async def fetch_github_issue_events(
    owner: str,
    repo: str,
    client: httpx.AsyncClient,
    since_days: int = 90,
    max_pages: int = 3,
) -> list[GitHubIssueEvent]:
    """Fetch recent issues AND pull requests, merged.

    Uses /issues?state=all&since=<now-since_days>. `since` filters on updated_at,
    which is always >= created_at and >= closed_at, so nothing created/closed in
    the window is missed. PRs are distinguished by the 'pull_request' key.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    events: list[GitHubIssueEvent] = []
    for page in range(1, max_pages + 1):
        try:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/issues",
                headers=_gh_headers(),
                params={
                    "state": "all",
                    "since": since,
                    "per_page": "100",
                    "page": str(page),
                    "sort": "updated",
                    "direction": "desc",
                },
            )
            resp.raise_for_status()
            batch = resp.json()
        except httpx.HTTPError:
            break

        if not batch:
            break

        for item in batch:
            created = _parse_gh_time(item.get("created_at"))
            if created is None:
                continue
            events.append(
                GitHubIssueEvent(
                    number=item.get("number", 0),
                    title=item.get("title", ""),
                    is_pull_request="pull_request" in item,
                    created_at=created,
                    closed_at=_parse_gh_time(item.get("closed_at")),
                    url=item.get("html_url", ""),
                )
            )

        if len(batch) < 100:
            break

    return events


async def fetch_github_stats_for_package(
    homepage: str,
    repository_url: str,
    client: httpx.AsyncClient | None = None,
) -> GitHubStats:
    """Fetch GitHub stats by deriving repo from package URLs."""
    repo = derive_github_repo([repository_url, homepage])
    if repo:
        return await fetch_github_stats(repo[0], repo[1], client=client)
    return GitHubStats()


async def fetch_github_extended_stats_for_package(
    homepage: str,
    repository_url: str,
    client: httpx.AsyncClient | None = None,
) -> tuple[GitHubStats, list[GitHubIssueEvent]]:
    """Derive the repo once, then fetch stats + signals + issue events in parallel."""
    repo = derive_github_repo([repository_url, homepage])
    if not repo:
        return GitHubStats(), []

    owner, name = repo
    if client is None:
        async with HttpClientFactory().create() as owned_client:
            return await fetch_github_extended_stats_for_package(
                homepage, repository_url, client=owned_client
            )
    stats, signals, events = await asyncio.gather(
        fetch_github_stats(owner, name, client=client),
        fetch_github_repo_signals(owner, name, client),
        fetch_github_issue_events(owner, name, client),
    )
    has_ci, has_readme = signals
    stats.has_ci = has_ci
    stats.has_readme = has_readme
    return stats, events


async def fetch_release_notes_for_package(
    homepage: str,
    repository_url: str,
    version: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Fetch release notes by deriving GitHub repo from package URLs."""
    repo = derive_github_repo([repository_url, homepage])
    if repo:
        owner, name = repo
        tag = f"v{version}" if not version.startswith("v") else version
        notes = await fetch_github_release_notes(owner, name, tag, client=client)
        if notes:
            return notes
        return await fetch_github_release_notes(owner, name, client=client)
    return ""
